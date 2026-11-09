# Copyright (C) 2025 European Union
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the European Union Public Licence (EUPL) v. 1.2
# as published by the European Union.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# European Union Public Licence for more details.
#
# You should have received a copy of the European Union Public Licence
# along with this program. If not, see <https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12>.

"""Evaluation orchestrator — configures and runs the evaluation pipeline."""

import asyncio
import importlib.util
import itertools
import json
import os
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from palace.agents import Agent
from palace.analyzers import CitationVerifier
from palace.analyzers.fetch import get_fetch_fn
from palace.evaluation.dispatch import dispatch_tasks
from palace.evaluation.judge_config import JudgeConfig
from palace.evaluation.renderers import select_renderer
from palace.task_types import Task
from palace.utils.constants import get_judge_key, get_judge_model, get_judge_url
from palace.utils.io_adapters import get_io_adapter, load_io_adapters
from palace.utils.model_extra_params import get_model_extra_params, load_model_extra_params
from palace.utils.paths import (
    BUNDLED_IO_ADAPTERS_FILE,
    BUNDLED_MODEL_EXTRA_PARAMS_FILE,
    LOGS_PATH,
    RESULTS_PATH,
    TASKLISTS_PATH,
    resolve_local_path,
)
from palace.utils.printing import print


def _stats_suffixes(values: list[float], ndigits: int) -> dict[str, float | None]:
    """Aggregate per-task values into _mean/_min/_p50/_p95/_max suffixed stats.

    Empty input yields all-None values (stable JSON shape). Percentiles use
    nearest-rank on the sorted list — deterministic, no numpy dependency:
    p50 is the median, p95 the nearest-rank 95th (tail-latency proxy for
    TTFT-style metrics where the mean hides slow outliers).
    """
    if not values:
        return {suffix: None for suffix in ("_mean", "_min", "_p50", "_p95", "_max")}
    ordered = sorted(values)
    n = len(ordered)

    def _nearest_rank(pct: float) -> float:
        rank = max(1, -(-pct * n // 100))  # ceil(pct/100 * n), min 1
        return ordered[rank - 1]

    return {
        "_mean": round(sum(ordered) / n, ndigits),
        "_min": round(ordered[0], ndigits),
        "_p50": round(_nearest_rank(50), ndigits),
        "_p95": round(_nearest_rank(95), ndigits),
        "_max": round(ordered[-1], ndigits),
    }


def compute_agent_metrics(report: dict[str, dict]) -> dict[str, float]:
    """Compute agent-execution metrics from an evaluation report.

    Calculates pass@k scores at k=1,3,6,10 for steps and tool calls,
    averages for numeric stats, and tool hallucination rate.

    Args:
        report: Mapping of task ID to task result dict containing
            agent execution stats (n_steps, n_toolcalls, etc.).

    Returns:
        Dict of computed metric names to float values.
    """
    agent_run_stats: list[dict[str, Any]] = [
        {"name": "n_steps", "pass@k": True, "pass@k_symbol": "s"},
        {"name": "n_toolcalls", "pass@k": True, "pass@k_symbol": "tc"},
        {"name": "n_tool_hallucinations"},
        {"name": "tools_list"},
        {"name": "tool_calls_list"},
    ]

    def _stat_present(name: str) -> bool:
        return any(name in r for r in report.values())

    metrics: dict[str, float] = {}

    for stat, k_value in itertools.product(
        [s for s in agent_run_stats if s.get("pass@k") and _stat_present(s["name"])],
        [1, 3, 6, 10],
    ):
        n_tasks = len([r for r in report.values() if stat["name"] in r])
        if n_tasks == 0:
            continue
        metrics[f"pass@{k_value}{stat['pass@k_symbol']}"] = (
            len([r for r in report.values() if r["is_correct"] and stat["name"] in r and r[stat["name"]] <= k_value])
            / n_tasks
        )

    for stat in agent_run_stats:
        if not stat.get("pass@k") or not _stat_present(stat["name"]):
            continue
        total = count = total_passed = count_passed = total_failed = count_failed = 0
        for r in report.values():
            if stat["name"] not in r:
                continue
            total += r[stat["name"]]
            count += 1
            if r["is_correct"]:
                total_passed += r[stat["name"]]
                count_passed += 1
            else:
                total_failed += r[stat["name"]]
                count_failed += 1
        if count > 0:
            metrics[f"avg_{stat['name']}"] = total / count
        if count_passed > 0:
            metrics[f"avg_{stat['name']}_passed"] = total_passed / count_passed
        if count_failed > 0:
            metrics[f"avg_{stat['name']}_failed"] = total_failed / count_failed

    if any("n_toolcalls" in r for r in report.values()):
        n_hallucinations = sum(r.get("n_tool_hallucinations", 0) for r in report.values())
        n_toolcalls = sum(r.get("n_toolcalls", 0) for r in report.values())
        metrics["tool_hallucination_rate"] = n_hallucinations / n_toolcalls if n_toolcalls > 0 else 0

    return metrics


class Evaluation:
    """Runs benchmark evaluations on models.

    Handles agent construction, task dispatch, verification, metrics computation,
    and result persistence.

    Args:
        name: Run name used for the output JSONL filename.
        url: API endpoint URL.
        token: API authentication token.
        endpoint_type: "openai", "azure", "mcp", or None (auto-detect).
        vivarium_url: Vivarium server URL for agentic execution.
        task_limit: Maximum number of tasks to evaluate per tasklist.
        task_offset: Number of tasks to skip from the beginning (default: 0).
        runs_per_configuration: Number of evaluation runs per model/tasklist pair.
        output_path: Directory for JSONL result files.
        on_task_complete: Optional callback invoked after each task with (current, total, result).
        on_task_state: Optional callback invoked on task state changes with (task_index, state_label).
        enable_citation_verifier: Enable the citation verifier analyzer.
        io_adapter: Optional model I/O adapter config dict.
        model_extra_params: Optional extra params dict to merge into API calls.
        report_detail: Level of detail in per-task report.
        concurrency: Number of tasks to run concurrently.
        judge_config: Optional JudgeConfig with judge endpoint URL, key, model, and extra params.
            If not provided, falls back to environment variables and config file settings.
        keep_last_env: Keep the last agentic environment alive for debugging (default: False).
    """

    def __init__(
        self,
        name: str = "eval",
        url: str = "",
        token: str | None = None,
        endpoint_type: str | None = None,
        agentic: bool | None = None,
        vivarium_url: str | None = None,
        task_limit: int | None = None,
        task_offset: int = 0,
        runs_per_configuration: int = 1,
        output_path: Path | None = None,
        on_task_complete: Callable[[int, int], None] | None = None,
        on_task_state: Callable[[int, str], None] | None = None,
        enable_citation_verifier: bool | None = None,
        io_adapter: dict | None = None,
        model_extra_params: dict | None = None,
        report_detail: str = "default",
        concurrency: int | None = None,
        judge_config: JudgeConfig | None = None,
        harness: str | None = None,
        keep_last_env: bool = False,
        untrusted_agent: bool = False,
    ):
        if report_detail not in ("none", "default", "full"):
            raise ValueError(f"report_detail must be 'none', 'default', or 'full', got '{report_detail}'")
        # Judge config: use provided config or build from environment/config defaults
        if judge_config:
            self.judge_config = judge_config
        else:
            self.judge_config = JudgeConfig(
                url=get_judge_url(),
                key=get_judge_key(),
                model=get_judge_model(),
            )
        # Note: judge_model can be None here — it's only required for task types that use LLM judging
        # (QA, CriteriaEvaluation). The Judge class will raise a clear error if needed.
        if concurrency is None:
            concurrency = int(os.environ.get("PALACE_CONCURRENCY", "25"))
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        self.name = name
        self.url = url
        self.token = token
        self.endpoint_type = endpoint_type
        self.agentic = agentic
        self.vivarium_url = vivarium_url
        self.task_limit = task_limit
        self.task_offset = task_offset
        self.runs_per_configuration = runs_per_configuration
        self.output_path = output_path or RESULTS_PATH
        self.on_task_complete = on_task_complete
        self.on_task_state = on_task_state
        self.io_adapter = io_adapter
        self.model_extra_params = model_extra_params
        self.report_detail = report_detail
        self.concurrency = concurrency

        # Initialize analyzers
        self.analyzers = []
        if enable_citation_verifier is None:
            enable_citation_verifier = os.getenv("ENABLE_CITATION_VERIFIER", "").lower() in ("true", "1", "yes")
        if enable_citation_verifier:
            self.analyzers.append(CitationVerifier(fetch_fn=get_fetch_fn()))

        self.harness = harness
        self.keep_last_env = keep_last_env
        self.untrusted_agent = untrusted_agent

    def _create_agent(self, model: str, tasklist_type: str, extra_params: dict | None = None) -> Agent:
        """Construct the appropriate agent for a model.

        agentic="auto": use VivariumAgent only for Agentic tasklists
        agentic=True: always use VivariumAgent
        agentic=False: never use VivariumAgent
        """
        use_vivarium = self.agentic is True or (self.agentic is None and tasklist_type == "Agentic")
        if use_vivarium:
            from palace.agents.vivarium_agent import VivariumAgent

            return VivariumAgent(
                name=model,
                url=self.url,
                token=self.token,
                vivarium_url=self.vivarium_url,
                extra_params=extra_params,
                harness=self.harness,
                keep_last_env=self.keep_last_env,
                untrusted_agent=self.untrusted_agent,
            )
        if self.endpoint_type == "mcp":
            from palace.agents.mcp_agent import MCPAgent

            return MCPAgent(url=self.url, token=self.token, name=model)
        from palace.agents.api_agent import APIAgent

        # Pass endpoint_type as api_type only if explicitly set (for azure, or to override auto-detection).
        # None lets APIAgent auto-detect from model name.
        return APIAgent(
            url=self.url, token=self.token, name=model, api_type=self.endpoint_type, extra_params=extra_params
        )

    def _print_evaluation_summary(self, model: str, tasklist: str, accuracy: float, metrics: dict) -> None:
        """Print a formatted evaluation summary box."""
        operational = metrics.get("operational", {})
        timing = operational.get("timing", {})
        throughput = operational.get("throughput", {})
        tokens = operational.get("tokens", {})

        # Build token/timing lines
        lines = []

        # Time line
        if timing.get("total_seconds"):
            lines.append(
                f":stopwatch: Time: [blue]{timing['total_seconds']:.1f}s[/] compute, "
                f"[blue]{timing.get('wall_seconds', 0):.1f}s[/] wall"
            )
        if timing.get("ttfc_seconds_mean") is not None:
            ttfc_line = f"Time to first chunk: [blue]{timing['ttfc_seconds_mean']:.2f}s[/] mean"
            if timing.get("ttfc_seconds_p95") is not None:
                ttfc_line += f" ([blue]{timing['ttfc_seconds_p95']:.2f}s[/] p95)"
            lines.append(ttfc_line)

        # Tokens line
        if tokens.get("output_tokens"):
            gen_throughput = throughput.get("generation_cps_mean")
            throughput_str = f" @ [blue]{gen_throughput:,.0f}[/] tok/s gen" if gen_throughput else ""
            lines.append(
                f":1234: Tokens: [blue]{tokens.get('total_tokens') or tokens['output_tokens']:,}[/] "
                f"({tokens.get('input_tokens') or 0:,} in / {tokens['output_tokens']:,} out){throughput_str}"
            )
        elif operational:
            lines.append(":1234: Tokens: [dim]N/A (not supported by endpoint)[/]")

        # Server-reported latency line (only when the endpoint provides a checkpoint)
        server = timing.get("server", {})
        if server.get("engine_ttft_seconds_mean") is not None:
            lines.append(
                f":globe_with_meridians: Server latency: "
                f"[blue]{server['engine_ttft_seconds_mean']:.2f}s[/] TTFT mean, "
                f"[blue]{server.get('engine_tbt_seconds_mean', 0) * 1000:.0f} ms[/] TBT mean"
            )

        # Judge tokens line
        judge = metrics.get("judge", {})
        if judge.get("total_tokens"):
            lines.append(f":scales: Judge tokens: [blue]{judge['total_tokens']:,}[/]")

        # Task outcome
        correct, evaluated = metrics["correct_count"], metrics["evaluated_count"]
        incorrect = evaluated - correct
        outcome = f"[green]{correct}[/] correct"
        if incorrect > 0:
            outcome += f", [red]{incorrect}[/] incorrect"
        outcome += f" ([blue]{accuracy * 100:.0f}%[/] accuracy)"

        # Skipped tasks
        errors, unsupported = metrics["error_count"], metrics["unsupported_count"]
        skipped_parts = []
        if errors > 0:
            skipped_parts.append(f"[yellow]{errors} errors[/]")
        if unsupported > 0:
            skipped_parts.append(f"[yellow]{unsupported} unsupported[/]")

        # Assemble output
        output = f"[blue]:robot: {model}[/] on :scroll: [blue]{tasklist}[/]\n\n:bar_chart: {outcome}"
        if skipped_parts:
            output += f"\n:warning: [dim]Skipped: {', '.join(skipped_parts)}[/]"
        if lines:
            output += "\n" + "\n".join(lines)

        print(output, box=True, box_title="Evaluation Report")

    def evaluate_all(self, models: list[str], tasklists: list[str]):
        """Run evaluations for all model/tasklist combinations. Prints and writes JSONL."""
        return asyncio.run(self.evaluate_all_async(models, tasklists))

    async def evaluate_all_async(self, models: list[str], tasklists: list[str]):
        """Async version of evaluate_all."""
        results = []

        grid = list(itertools.product(models, tasklists))
        for model, tasklist in grid:
            for run in range(self.runs_per_configuration):
                print(f"""
[bold]Evaluating (run [blue]{run + 1}/{self.runs_per_configuration}[/])
:robot: agent [blue] {model}[/]
:scroll: on tasklist [blue]{tasklist}[/]
:scales: judge [blue]{self.judge_config.model or "default"}[/]
""")

                accuracy, metrics, report = await self.evaluate_async(model, tasklist)

                print()
                self._print_evaluation_summary(model, tasklist, accuracy, metrics)

                run_results = {
                    "model": model,
                    "tasklist": tasklist,
                    "accuracy": accuracy,
                    "metrics": metrics,
                    "agentic": bool(metrics.get("agent")),  # True only if agent dict has content
                }
                if self.report_detail != "none":
                    run_results["detailed_report"] = report
                results.append(run_results)

                os.makedirs(self.output_path, exist_ok=True)
                output_file = self.output_path / f"{self.name}.jsonl"
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(run_results, ensure_ascii=False) + "\n")

                print(f"[dim]Results saved to {output_file}[/dim]")

        return pd.DataFrame(results)

    def evaluate(self, model: str, tasklist: str) -> tuple[float, dict, dict[str, dict]]:
        """Evaluate a model on a tasklist. Returns (accuracy, metrics, report)."""
        return asyncio.run(self.evaluate_async(model, tasklist))

    async def evaluate_async(self, model: str, tasklist: str) -> tuple[float, dict, dict[str, dict]]:
        """Async: run model on tasklist, verify, compute metrics. Returns (accuracy, metrics, report)."""
        tasklist_path = resolve_local_path(tasklist)

        if not tasklist_path:
            available = [t.name for t in TASKLISTS_PATH.iterdir() if t.is_dir()]
            raise FileNotFoundError(
                f"Tasklist '{tasklist}' not found. "
                f"Available tasklists: {', '.join(sorted(available)) if available else 'none (run `palace download` first)'}. "
                f"Note: tasklist names are case-sensitive."
            )

        with open(tasklist_path / "info.json") as f:
            tasklist_info = json.load(f)

        # Resolve task class
        from palace.task_types.agentic import AgenticTask
        from palace.task_types.classification import ClassificationTask
        from palace.task_types.criteria_evaluation import CriteriaEvaluationTask
        from palace.task_types.instruction_following import InstructionFollowingTask
        from palace.task_types.qa import QATask

        task_type_map = {
            "QA": QATask,
            "Classification": ClassificationTask,
            "Criteria Evaluation": CriteriaEvaluationTask,
            "Instruction Following": InstructionFollowingTask,
            "Agentic": AgenticTask,
        }
        task_cls = task_type_map.get(tasklist_info["task_type"], Task)

        # Create agent
        file_extra_params = load_model_extra_params()
        bundled_extra_params = load_model_extra_params(BUNDLED_MODEL_EXTRA_PARAMS_FILE)
        extra_params_result = get_model_extra_params(
            model, self.model_extra_params, file_extra_params, bundled_extra_params
        )
        if extra_params_result is not None:
            resolved_extra_params, extra_params_source = extra_params_result
            print(f"[blue]:gear: Using extra params for {model} ({extra_params_source}): {resolved_extra_params}[/]")
        else:
            resolved_extra_params = None

        agent = self._create_agent(model, tasklist_info["task_type"], extra_params=resolved_extra_params)

        # Load tasks
        tasks_path = tasklist_info.get("tasks_path", "tasks.json")
        json_tasks = []
        for p in sorted(tasklist_path.glob(tasks_path)):
            if not p.is_file():
                continue
            with open(p) as f:
                data = json.load(f)
            if isinstance(data, list):
                json_tasks.extend(data)
            else:
                json_tasks.append(data)
        objective_template = tasklist_info.get("objective_template", "{{objective}}")
        tasks: list[Task] = [
            Task.from_dict(
                task
                | {
                    "task_type": tasklist_info["task_type"],
                    "task_type_fields": tasklist_info.get("task_type_fields", {}) | task.get("task_type_fields", {}),
                    "_objective_template": objective_template,
                }
            )
            for task in json_tasks
        ]

        # Resolve task_files search directories
        task_files_path = tasklist_info.get("task_files_path", "task_files")
        task_files_dirs = sorted(d for d in tasklist_path.glob(task_files_path) if d.is_dir())

        # Set verify_fn on AgenticTasks
        if tasklist_info["task_type"] == "Agentic":
            # Discover environments via spec.json
            env_dir = tasklist_path / "environment"
            env_paths: dict[str, Path] = {}

            # Check for spec.json files
            if env_dir.is_dir():
                # Multi-env: environment/*/spec.json
                multi_envs = {d.name: d for d in env_dir.iterdir() if d.is_dir() and (d / "spec.json").exists()}
                # Single-env: environment/spec.json
                single_env = (env_dir / "spec.json").exists()

                if multi_envs:
                    env_paths = multi_envs
                elif single_env:
                    env_paths = {"default": env_dir}
                else:
                    # No spec.json — use vivarium's default spec
                    env_paths = {"default": env_dir}

            verify_fns: dict[str, object] = {}
            # For multi-env, verify.py may be in environment/ root (shared) or per-env subdir
            shared_verify_path = env_dir / "verify.py"
            shared_verify_fn = _load_verify_fn(shared_verify_path) if shared_verify_path.exists() else None

            for task in tasks:
                env_name = task.custom_fields.get("env") or next(iter(env_paths), "default")
                env_path = env_paths.get(env_name, env_dir)
                env_path_str = str(env_path)
                if env_path_str not in verify_fns:
                    # Check per-env verify.py first, fall back to shared
                    per_env_verify = env_path / "verify.py"
                    if per_env_verify.exists():
                        verify_fns[env_path_str] = _load_verify_fn(per_env_verify)
                    else:
                        verify_fns[env_path_str] = shared_verify_fn
                task._verify_fn = verify_fns[env_path_str]  # type: ignore[attr-defined]
                task._tasklist_path = tasklist_path  # type: ignore[attr-defined]

        # Slice tasks by offset and limit
        if self.task_offset > 0:
            tasks = tasks[self.task_offset :]
        if self.task_limit is not None:
            tasks = tasks[: self.task_limit]

        # Resolve adapter
        file_io_adapters = load_io_adapters()
        bundled_io_adapters = load_io_adapters(BUNDLED_IO_ADAPTERS_FILE)
        result = get_io_adapter(agent.name, self.io_adapter, file_io_adapters, bundled_io_adapters)
        if result is not None:
            adapter, source = result
            print(f"[blue]:wrench: Using I/O adapter for {agent.name} ({source})[/]")
        else:
            adapter = None

        # Select renderer and dispatch
        log_path = LOGS_PATH / f"{self.name}.log"
        renderer = select_renderer(len(tasks), self.concurrency, log_path=log_path)

        if self.concurrency > 1:
            agent.verbose = False

        # Judge preflight: QA and Criteria Evaluation verify via an LLM judge
        # constructed lazily inside the first task's verify(). Validate the
        # configuration here instead — misconfiguration then costs seconds,
        # not one completed agent run.
        if tasklist_info["task_type"] in ("QA", "Criteria Evaluation"):
            from palace.judge import validate_judge_config

            judge_config = self.judge_config
            judge_model = (judge_config.model if judge_config else None) or get_judge_model()
            judge_url = (judge_config.url if judge_config else None) or get_judge_url()
            validate_judge_config(judge_model, judge_url)

        task_results = await dispatch_tasks(
            tasks=tasks,
            agent=agent,
            adapter=adapter,
            tasklist_path=tasklist_path,
            tasklist_info=tasklist_info,
            task_files_dirs=task_files_dirs,
            analyzers=self.analyzers,
            concurrency=self.concurrency,
            detail=self.report_detail,
            renderer=renderer,
            on_task_complete=self.on_task_complete,
            on_task_state=self.on_task_state,
            judge_config=self.judge_config,
        )

        # Build report and compute metrics
        report = {r.task_id: r.report_entry for r in task_results}
        verification_results = [r.verification for r in task_results]

        penalize_unsupported = tasklist_info.get("penalize_unsupported", False)
        evaluated = [r for r in verification_results if not r.is_skipped]
        error_results = [r for r in verification_results if r.outcome == "error"]
        unsupported_results = [r for r in verification_results if r.outcome == "unsupported"]
        task_type_metrics = task_cls.aggregate(verification_results, penalize_unsupported=penalize_unsupported)
        accuracy = round(task_type_metrics.pop("accuracy", 0), 4)
        evaluated_report = {k: v for k, v in report.items() if not v.get("is_skipped")}
        agent_metrics = compute_agent_metrics(evaluated_report)

        metrics: dict[str, Any] = {
            "task_count": len(report),
            "evaluated_count": len(evaluated),
            "correct_count": sum(r.is_correct for r in evaluated),
            "skipped_count": len(error_results) + len(unsupported_results),
            "error_count": len(error_results),
            "unsupported_count": len(unsupported_results),
            "accuracy": accuracy,
            "task_type": task_type_metrics,
            "agent": agent_metrics,
        }

        # Aggregate operational metrics from all tasks
        wall_seconds = 0.0
        total_input_tokens = 0
        total_output_tokens = 0
        total_compute_seconds = 0.0
        judge_input_tokens = 0
        judge_output_tokens = 0
        judge_compute_seconds = 0.0
        # Client-measured per-task values
        ttfc_values: list[float] = []
        ttfcc_values: list[float] = []
        # Client-derived per-task rates, keyed by throughput field name
        _THROUGHPUT_BUCKETS: dict[str, list[float]] = {
            "prefill_cps": [],
            "generation_cps": [],
            "content_cps": [],
            "total_cps": [],
        }
        # Server-reported values (seconds), keyed by field name
        _SERVER_BUCKETS: dict[str, list[float]] = {
            "engine_ttft_seconds": [],
            "service_ttft_seconds": [],
            "user_visible_ttft_seconds": [],
            "pre_inference_seconds": [],
            "engine_tbt_seconds": [],
            "service_tbt_seconds": [],
            "engine_ttlt_seconds": [],
        }
        has_token_data = False
        has_timing_data = False
        attempt_values: list[int] = []

        for entry in report.values():
            # Agent tokens (from entry["operational"]["tokens"])
            operational = entry.get("operational", {})
            tokens = operational.get("tokens", {})
            if tokens.get("input_tokens") is not None:
                total_input_tokens += tokens["input_tokens"]
                has_token_data = True
            if tokens.get("output_tokens") is not None:
                total_output_tokens += tokens["output_tokens"]
            if operational.get("attempts") is not None:
                attempt_values.append(operational["attempts"])

            # Agent timing (from entry["operational"]["timing"])
            timing = operational.get("timing", {})
            if timing.get("wall_seconds") is not None:
                wall_seconds += timing["wall_seconds"]
            if timing.get("total_seconds") is not None:
                total_compute_seconds += timing["total_seconds"]
                has_timing_data = True
            if timing.get("ttfc_seconds") is not None:
                ttfc_values.append(timing["ttfc_seconds"])
            if timing.get("ttfcc_seconds") is not None:
                ttfcc_values.append(timing["ttfcc_seconds"])
            server = timing.get("server", {})
            for key, bucket in _THROUGHPUT_BUCKETS.items():
                value = operational.get("throughput", {}).get(key)
                if value is not None:
                    bucket.append(value)
            for key, bucket in _SERVER_BUCKETS.items():
                value = server.get(key)
                if value is not None:
                    bucket.append(value)

            # Judge tokens (from verification metrics["judge"])
            judge_stats = entry.get("metrics", {}).get("judge")
            if judge_stats:
                if judge_stats.get("input_tokens") is not None:
                    judge_input_tokens += judge_stats["input_tokens"]
                if judge_stats.get("output_tokens") is not None:
                    judge_output_tokens += judge_stats["output_tokens"]
                if judge_stats.get("compute_seconds") is not None:
                    judge_compute_seconds += judge_stats["compute_seconds"]

        # Add token metrics if we have data (even if tokens are 0, timing is useful)
        if has_token_data or has_timing_data:
            total_tokens = total_input_tokens + total_output_tokens if has_token_data else None
            # Percentiles add tail visibility to mean/min/max; nearest-rank
            # over per-task values, same population as the other suffixes.
            ttfc_stats = _stats_suffixes(ttfc_values, 2)
            ttfcc_stats = _stats_suffixes(ttfcc_values, 2)
            metrics["operational"] = {
                "reasoning_status": next(
                    (
                        e.get("operational", {}).get("reasoning_status")
                        for e in report.values()
                        if e.get("operational", {}).get("reasoning_status") is not None
                    ),
                    None,
                ),
                "timing": {
                    "total_seconds": round(total_compute_seconds, 2),
                    "wall_seconds": round(wall_seconds, 2),
                    # Client-measured aggregates (mean/min/p50/p95/max over
                    # per-task values)
                    **{f"ttfc_seconds{k}": v for k, v in ttfc_stats.items()},
                    **{f"ttfcc_seconds{k}": v for k, v in ttfcc_stats.items()},
                    "server": {
                        f"{key}{suffix}": None
                        for key in _SERVER_BUCKETS
                        for suffix in ("_mean", "_min", "_p50", "_p95", "_max")
                    },
                },
                "throughput": {
                    f"{key}{suffix}": None
                    for key in _THROUGHPUT_BUCKETS
                    for suffix in ("_mean", "_min", "_p50", "_p95", "_max")
                },
                "tokens": {
                    "input_tokens": total_input_tokens if has_token_data else None,
                    "output_tokens": total_output_tokens if has_token_data else None,
                    "total_tokens": total_tokens,
                },
                # Retry visibility: attempts per task summed/maxed across the
                # run. 1 × task_count means a retry-free run; max > 1 flags
                # retry-heavy endpoints. Null when no task reported it.
                "attempts": {
                    "total": sum(attempt_values) if attempt_values else None,
                    "max": max(attempt_values) if attempt_values else None,
                },
            }
            for key, values in _THROUGHPUT_BUCKETS.items():
                if values:
                    stats = _stats_suffixes(values, 1)
                    metrics["operational"]["throughput"].update({f"{key}{k}": v for k, v in stats.items()})
            # Server-reported aggregates (authoritative when present; values
            # None on endpoints without a checkpoint — identical shape everywhere)
            for key, values in _SERVER_BUCKETS.items():
                if values:
                    stats = _stats_suffixes(values, 4)
                    out_server = metrics["operational"]["timing"]["server"]
                    out_server.update({f"{key}{k}": v for k, v in stats.items()})
            # Judge stats (include even if tokens are 0/None for display purposes)
            if judge_compute_seconds > 0 or judge_input_tokens > 0 or judge_output_tokens > 0:
                judge_total = (
                    judge_input_tokens + judge_output_tokens
                    if (judge_input_tokens > 0 or judge_output_tokens > 0)
                    else None
                )
                metrics["judge"] = {
                    "input_tokens": judge_input_tokens if judge_total else None,
                    "output_tokens": judge_output_tokens if judge_total else None,
                    "total_tokens": judge_total,
                    "compute_seconds": round(judge_compute_seconds, 2),
                }

        # Per-group breakdown
        groups: dict[str, list] = {}
        for task, result in zip(tasks, task_results):
            group = task.group
            if group:
                groups.setdefault(group, []).append(result.verification)
        if groups:
            metrics["per_group"] = {
                g: task_cls.aggregate(vrs, penalize_unsupported=penalize_unsupported) for g, vrs in groups.items()
            }

        return accuracy, metrics, report


def _load_verify_fn(path: Path) -> Callable | None:
    """Load verify function from a Python file. Returns None if file doesn't exist."""
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "verify", None)


def evaluate(
    run_name: str,
    url: str,
    token: str | None,
    name: str,
    tasklist: str | list[str],
    *,
    output_folder: str | Path | None = None,
    limit: int | None = None,
    runs_per_configuration: int = 1,
    on_task_complete: Callable[[int, int], None] | None = None,
    endpoint_type: str | None = None,
    io_adapter: dict | None = None,
    model_extra_params: dict | None = None,
    report_detail: str = "default",
    agentic: bool | None = None,
    concurrency: int | None = None,
    vivarium_url: str | None = None,
    judge_config: JudgeConfig | None = None,
    harness: str | None = None,
    untrusted_agent: bool = False,
):
    """Evaluate a model on tasklists. Convenience function wrapping Evaluation class.

    Args:
        harness: Agent harness for vivarium execution ("builtin", "pi", "omp"). Default: "omp".
        untrusted_agent: Enable hardened verification mode (destroy and recreate env before verify).
    """
    output_path = Path(output_folder) if output_folder else RESULTS_PATH
    evaluation = Evaluation(
        name=run_name,
        url=url,
        token=token,
        endpoint_type=endpoint_type,
        agentic=agentic,
        vivarium_url=vivarium_url,
        task_limit=limit,
        runs_per_configuration=runs_per_configuration,
        output_path=output_path,
        on_task_complete=on_task_complete,
        io_adapter=io_adapter,
        model_extra_params=model_extra_params,
        report_detail=report_detail,
        concurrency=concurrency,
        judge_config=judge_config,
        harness=harness,
        untrusted_agent=untrusted_agent,
    )
    tasklist_list = [tasklist] if isinstance(tasklist, str) else tasklist
    return evaluation.evaluate_all([name], tasklist_list)
