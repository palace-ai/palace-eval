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
from palace.evaluation.renderers import select_renderer
from palace.task_types import Task
from palace.utils.constants import get_judge_model
from palace.utils.io_adapters import get_io_adapter, load_io_adapters
from palace.utils.model_extra_params import get_model_extra_params, load_model_extra_params
from palace.utils.paths import (
    BUNDLED_IO_ADAPTERS_FILE,
    BUNDLED_MODEL_EXTRA_PARAMS_FILE,
    LOGS_PATH,
    RESULTS_PATH,
    TASKLISTS_PATH,
)
from palace.utils.printing import print


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


def _check_endpoint(url: str, token: str | None) -> None:
    """Verify LLM endpoint is reachable. Raises RuntimeError if not."""
    import httpx

    try:
        httpx.get(f"{url}/models", headers={"Authorization": f"Bearer {token}"} if token else {}, timeout=10)
    except httpx.ConnectError as e:
        raise RuntimeError(f"Cannot reach LLM endpoint: {url}\n  {e}") from e
    except httpx.TimeoutException as e:
        raise RuntimeError(f"LLM endpoint timed out: {url}\n  {e}") from e
    except Exception:
        pass  # Other errors (401, 404, etc.) mean the endpoint is reachable


class Evaluation:
    """Runs benchmark evaluations on models.

    Handles agent construction, task dispatch, verification, metrics computation,
    and result persistence.

    Args:
        name: Run name used for the output JSONL filename.
        url: API endpoint URL.
        token: API authentication token.
        endpoint_type: "openai", "azure", or "mcp".
        vivarium_url: Vivarium server URL for agentic execution.
        task_amount_limit: Maximum number of tasks to evaluate per tasklist.
        runs_per_configuration: Number of evaluation runs per model/tasklist pair.
        output_path: Directory for JSONL result files.
        on_task_complete: Optional callback invoked after each task with (current, total, result).
        on_task_state: Optional callback invoked on task state changes with (task_index, state_label).
        enable_citation_verifier: Enable the citation verifier analyzer.
        io_adapter: Optional model I/O adapter config dict.
        model_extra_params: Optional extra params dict to merge into API calls.
        report_detail: Level of detail in per-task report.
        concurrency: Number of tasks to run concurrently.
    """

    def __init__(
        self,
        name: str = "eval",
        url: str = "",
        token: str | None = None,
        endpoint_type: str = "openai",
        agentic: bool | None = None,
        vivarium_url: str | None = None,
        task_amount_limit: int | None = None,
        runs_per_configuration: int = 1,
        output_path: Path | None = None,
        on_task_complete: Callable[[int, int], None] | None = None,
        on_task_state: Callable[[int, str], None] | None = None,
        enable_citation_verifier: bool | None = None,
        io_adapter: dict | None = None,
        model_extra_params: dict | None = None,
        report_detail: str = "default",
        concurrency: int | None = None,
    ):
        if report_detail not in ("none", "default", "full"):
            raise ValueError(f"report_detail must be 'none', 'default', or 'full', got '{report_detail}'")
        self.judge_model = get_judge_model()
        if not self.judge_model:
            raise ValueError("judge_model is required but not set. Set it with: palace config set judge_model <model>")
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
        self.task_amount_limit = task_amount_limit
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

    def _create_agent(self, model: str, tasklist_type: str, extra_params: dict | None = None) -> Agent:
        """Construct the appropriate agent for a model.

        agentic="auto": use VivariumAgent only for Agentic tasklists
        agentic=True: always use VivariumAgent
        agentic=False: never use VivariumAgent
        """
        use_vivarium = self.agentic is True or (self.agentic is None and tasklist_type == "Agentic")
        if use_vivarium:
            from palace.agents.vivarium_agent import VivariumAgent

            return VivariumAgent(name=model, url=self.url, token=self.token, vivarium_url=self.vivarium_url)
        if self.endpoint_type == "mcp":
            from palace.agents.mcp_agent import MCPAgent

            return MCPAgent(url=self.url, token=self.token, name=model)
        from palace.agents.api_agent import APIAgent

        return APIAgent(
            url=self.url, token=self.token, name=model, api_type=self.endpoint_type, extra_params=extra_params
        )

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
:scales: judge [blue]{self.judge_model}[/]
""")

                accuracy, metrics, report = await self.evaluate_async(model, tasklist)

                print()
                print(
                    f"[blue]:robot: {model}[/]:\n"
                    + f"on :scroll: [blue]{tasklist}[/]\n\n"
                    + f"[blue]{metrics['correct_count']}[/] / [blue]{metrics['evaluated_count']}[/] ([blue]{accuracy * 100:.0f}%[/])[/] tasks completed successfully."
                    + (
                        f" [yellow]({metrics['error_count']} errors, {metrics['unsupported_count']} unsupported)[/]"
                        if metrics.get("skipped_count")
                        else ""
                    )
                    + f"\nTotal time: [blue]{metrics['total_time']}[/]",
                    box=True,
                    box_title="Evaluation Report",
                )

                run_results = {
                    "model": model,
                    "tasklist": tasklist,
                    "accuracy": accuracy,
                    "metrics": metrics,
                    "agentic": metrics.get("agent") is not None,
                }
                if self.report_detail != "none":
                    run_results["detailed_report"] = report
                results.append(run_results)

                os.makedirs(self.output_path, exist_ok=True)
                with open(self.output_path / f"{self.name}.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(run_results, ensure_ascii=False) + "\n")

        return pd.DataFrame(results)

    def evaluate(self, model: str, tasklist: str) -> tuple[float, dict, dict[str, dict]]:
        """Evaluate a model on a tasklist. Returns (accuracy, metrics, report)."""
        return asyncio.run(self.evaluate_async(model, tasklist))

    async def evaluate_async(self, model: str, tasklist: str) -> tuple[float, dict, dict[str, dict]]:
        """Async: run model on tasklist, verify, compute metrics. Returns (accuracy, metrics, report)."""
        tasklist_path = TASKLISTS_PATH / tasklist

        if not tasklist_path.exists():
            available = [t.name for t in TASKLISTS_PATH.iterdir() if t.is_dir()]
            raise FileNotFoundError(
                f"Tasklist '{tasklist}' not found. "
                f"Available tasklists: {', '.join(sorted(available)) if available else 'none (run palace-download first)'}. "
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

        # Pre-check: verify LLM endpoint is reachable
        _check_endpoint(self.url, self.token)

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
        tasks: list[Task] = [
            Task.from_dict(
                task
                | {
                    "task_type": tasklist_info["task_type"],
                    "task_type_fields": tasklist_info.get("task_type_fields", {}) | task.get("task_type_fields", {}),
                }
            )
            for task in json_tasks
        ]

        # Resolve task_files search directories
        task_files_path = tasklist_info.get("task_files_path", "task_files")
        task_files_dirs = sorted(d for d in tasklist_path.glob(task_files_path) if d.is_dir())

        # Set verify_fn on AgenticTasks
        if tasklist_info["task_type"] == "Agentic":
            env_configs = tasklist_info.get("env", {})
            verify_fns: dict[str, object] = {}
            for task in tasks:
                env_name = task.custom_fields.get("env") or next(iter(env_configs), None)
                env_path = env_configs.get(env_name, {}).get("path", "environment") if env_name else "environment"
                if env_path not in verify_fns:
                    verify_fns[env_path] = _load_verify_fn(tasklist_path / env_path / "verify.py")
                task._verify_fn = verify_fns[env_path]  # type: ignore[attr-defined]
                task._tasklist_path = tasklist_path  # type: ignore[attr-defined]

        # Limit tasks
        if self.task_amount_limit is not None:
            tasks = tasks[: self.task_amount_limit]

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
        )

        # Build report and compute metrics
        report = {r.task_id: r.report_entry for r in task_results}
        verification_results = [r.verification for r in task_results]

        penalize_unsupported = tasklist_info.get("penalize_unsupported", False)
        evaluated = [r for r in verification_results if not r.is_skipped]
        error_results = [r for r in verification_results if r.outcome == "error"]
        unsupported_results = [r for r in verification_results if r.outcome == "unsupported"]
        task_type_metrics = task_cls.aggregate(verification_results, penalize_unsupported=penalize_unsupported)
        accuracy = task_type_metrics.pop("accuracy", 0)
        evaluated_report = {k: v for k, v in report.items() if not v.get("is_skipped")}
        agent_metrics = compute_agent_metrics(evaluated_report)

        metrics: dict[str, Any] = {
            "task_count": len(report),
            "evaluated_count": len(evaluated),
            "correct_count": sum(r.is_correct for r in evaluated),
            "skipped_count": len(error_results) + len(unsupported_results),
            "error_count": len(error_results),
            "unsupported_count": len(unsupported_results),
            "total_time": sum(t["elapsed_time"] for t in report.values()),
            "accuracy": accuracy,
            "task_type": task_type_metrics,
            "agent": agent_metrics,
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
    endpoint_type: str = "openai",
    io_adapter: dict | None = None,
    model_extra_params: dict | None = None,
    report_detail: str = "default",
    agentic: bool | None = None,
    concurrency: int | None = None,
    vivarium_url: str | None = None,
):
    """Evaluate a model on tasklists. Convenience function wrapping Evaluation class."""
    output_path = Path(output_folder) if output_folder else RESULTS_PATH
    evaluation = Evaluation(
        name=run_name,
        url=url,
        token=token,
        endpoint_type=endpoint_type,
        agentic=agentic,
        vivarium_url=vivarium_url,
        task_amount_limit=limit,
        runs_per_configuration=runs_per_configuration,
        output_path=output_path,
        on_task_complete=on_task_complete,
        io_adapter=io_adapter,
        model_extra_params=model_extra_params,
        report_detail=report_detail,
        concurrency=concurrency,
    )
    tasklist_list = [tasklist] if isinstance(tasklist, str) else tasklist
    return evaluation.evaluate_all([name], tasklist_list)
