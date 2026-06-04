"""Evaluation orchestrator — configures and runs the evaluation pipeline."""

import asyncio
import importlib.util
import itertools
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from palace.agents import Agent
from palace.analyzers import CitationVerifier
from palace.analyzers.fetch import get_fetch_fn
from palace.evaluation.dispatch import dispatch_tasks
from palace.evaluation.renderers import select_renderer
from palace.evaluation.types import TaskResult
from palace.task_types import Task, TaskVerificationResult
from palace.utils.constants import JUDGE_MODEL
from palace.utils.io_adapters import get_io_adapter, load_io_adapters
from palace.utils.paths import BUNDLED_IO_ADAPTERS_FILE, LOGS_PATH, RESULTS_PATH, TASKLISTS_PATH
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


class Evaluation:
    """Runs benchmark evaluations across agents and tasklists.

    Orchestrates the evaluation loop: loads tasks, dispatches them to agents,
    verifies answers, runs analyzers, computes metrics, and writes JSONL results.

    Args:
        name: Run name used for the output JSONL filename.
        task_amount_limit: Maximum number of tasks to evaluate per tasklist.
        runs_per_configuration: Number of evaluation runs per agent/tasklist pair.
        output_path: Directory for JSONL result files.
        on_task_complete: Optional callback invoked after each task with (current, total).
        enable_citation_verifier: Enable the citation verifier analyzer.
        io_adapter: Optional model I/O adapter config dict.
        report_detail: Level of detail in per-task report.
        concurrency: Number of tasks to run concurrently.
    """

    def __init__(
        self,
        name: str = "eval",
        task_amount_limit: int | None = None,
        runs_per_configuration: int = 1,
        output_path: Path | None = None,
        on_task_complete: Callable[[int, int], None] | None = None,
        enable_citation_verifier: bool | None = None,
        io_adapter: dict | None = None,
        report_detail: str = "default",
        concurrency: int | None = None,
    ):
        if report_detail not in ("none", "default", "full"):
            raise ValueError(f"report_detail must be 'none', 'default', or 'full', got '{report_detail}'")
        if concurrency is None:
            concurrency = int(os.environ.get("PALACE_CONCURRENCY", "1"))
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        self.name = name
        self.task_amount_limit = task_amount_limit
        self.runs_per_configuration = runs_per_configuration
        self.output_path = output_path or RESULTS_PATH
        self.on_task_complete = on_task_complete
        self.io_adapter = io_adapter
        self.report_detail = report_detail
        self.concurrency = concurrency

        # Initialize analyzers
        self.analyzers = []
        if enable_citation_verifier is None:
            enable_citation_verifier = os.getenv("ENABLE_CITATION_VERIFIER", "").lower() in ("true", "1", "yes")
        if enable_citation_verifier:
            self.analyzers.append(CitationVerifier(fetch_fn=get_fetch_fn()))

    def evaluate_all(self, agents: list[Agent], tasklists: list[str]):
        """Run evaluations for all agent/tasklist combinations."""
        results = []

        grid = list(itertools.product(agents, tasklists))
        for agent, tasklist in grid:
            for run in range(self.runs_per_configuration):
                print(f"""
[bold]Evaluating (run [blue]{run + 1}/{self.runs_per_configuration}[/])
:robot: agent [blue] {agent.name}[/]
:scroll: on tasklist [blue]{tasklist}[/]
:scales: judge [blue]{JUDGE_MODEL}[/]
""")

                report, verification_results, task_cls = self.evaluate(agent, tasklist)

                evaluated = [r for r in verification_results if not r.is_skipped]
                skipped = [r for r in verification_results if r.is_skipped]
                correct_tasks = sum(r.is_correct for r in evaluated)
                total_time = sum(t["elapsed_time"] for t in report.values())

                task_type_metrics = task_cls.aggregate(verification_results)
                accuracy = task_type_metrics.pop("accuracy", 0)

                evaluated_report = {k: v for k, v in report.items() if not v.get("is_skipped")}
                agent_metrics = compute_agent_metrics(evaluated_report)

                print()
                print(
                    f"[blue]:robot: {agent.name}[/]:\n"
                    + f"on :scroll: [blue]{tasklist}[/]\n\n"
                    + f"[blue]{correct_tasks}[/] / [blue]{len(evaluated)}[/] ([blue]{accuracy * 100:.0f}%[/])[/] tasks completed successfully."
                    + (f" [yellow]({len(skipped)} skipped)[/]" if skipped else "")
                    + f"\nTotal time: [blue]{total_time}[/]",
                    box=True,
                    box_title="Evaluation Report",
                )

                metrics: dict[str, int | float | dict] = {
                    "task_count": len(report),
                    "evaluated_count": len(evaluated),
                    "correct_count": correct_tasks,
                    "skipped_count": len(skipped),
                    "total_time": total_time,
                    "accuracy": accuracy,
                    "task_type": task_type_metrics,
                    "agent": agent_metrics,
                }

                run_results = {
                    "model": agent.name,
                    "tasklist": tasklist,
                    "accuracy": accuracy,
                    "metrics": metrics,
                }
                if self.report_detail != "none":
                    run_results["detailed_report"] = report
                results.append(run_results)

                os.makedirs(self.output_path, exist_ok=True)
                with open(self.output_path / f"{self.name}.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(run_results, ensure_ascii=False) + "\n")

        return pd.DataFrame(results)

    def evaluate(
        self,
        agent: Agent,
        tasklist: str,
    ) -> tuple[dict[str, dict], list[TaskVerificationResult], type[Task]]:
        """Evaluate a single agent on a single tasklist."""
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

        # Route through vivarium for agentic tasklists
        if tasklist_info["task_type"] == "Agentic":
            try:
                from palace.agents.vivarium_agent import VivariumAgent
            except ImportError:
                raise RuntimeError(
                    "Agentic evaluation requires vivarium. "
                    "Install with:\n"
                    "  git clone https://gitlab.jrc.ec.europa.eu/jrc-projects/jrc-gpt/research/vivarium.git\n"
                    "  uv pip install -e vivarium/"
                )
            if not isinstance(agent, VivariumAgent):
                agent = VivariumAgent(
                    name=agent.name,
                    url=getattr(agent, "url", ""),
                    token=getattr(agent, "token", None),
                )

        # Load tasks
        with open(tasklist_path / "tasks.json") as f:
            json_tasks = json.load(f)
        tasks: list[Task] = [
            Task.from_dict(
                task | {
                    "task_type": tasklist_info["task_type"],
                    "task_type_fields": tasklist_info.get("task_type_fields", {}) | task.get("task_type_fields", {}),
                }
            )
            for task in json_tasks
        ]

        # Set verify_fn on AgenticTasks (orchestrator responsibility)
        if tasklist_info["task_type"] == "Agentic":
            verify_fn = _load_verify_fn(tasklist_path / "environment" / "verify.py")
            for task in tasks:
                task._verify_fn = verify_fn  # type: ignore[attr-defined]
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

        # Suppress agent trace output in concurrent mode
        if self.concurrency > 1:
            agent.verbose = False

        task_results = asyncio.run(
            dispatch_tasks(
                tasks=tasks,
                agent=agent,
                adapter=adapter,
                tasklist_path=tasklist_path,
                tasklist_info=tasklist_info,
                analyzers=self.analyzers,
                concurrency=self.concurrency,
                detail=self.report_detail,
                renderer=renderer,
                on_task_complete=self.on_task_complete,
            )
        )

        # Build outputs
        report = {r.task_id: r.report_entry for r in task_results}
        verification_results = [r.verification for r in task_results]
        return report, verification_results, task_cls


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
