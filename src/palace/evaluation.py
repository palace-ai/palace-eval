"""Core evaluation engine for running benchmarks on LLM agents."""

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
from palace.task_types import Task, TaskVerificationResult
from palace.utils.constants import JUDGE_MODEL
from palace.utils.exceptions import ConvergenceError
from palace.utils.io_adapters import get_io_adapter, load_io_adapters
from palace.utils.multimodal import is_image_attachment
from palace.utils.paths import BUNDLED_IO_ADAPTERS_FILE, RESULTS_PATH, TASKLISTS_PATH
from palace.utils.printing import PersistentStatus, loading, print


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

    # pass@k scores
    for stat, k_value in itertools.product(
        [s for s in agent_run_stats if s.get("pass@k") and _stat_present(s["name"])],
        [1, 3, 6, 10],
    ):
        n_tasks = len([r for r in report.values() if stat["name"] in r])
        if n_tasks == 0:
            continue
        metrics[f"pass@{k_value}{stat['pass@k_symbol']}"] = (
            len(
                [
                    r
                    for r in report.values()
                    if r["is_correct"]
                    and stat["name"] in r
                    and r[stat["name"]] <= k_value
                ]
            )
            / n_tasks
        )

    # metric averages (overall, passed, failed)
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

    # tool hallucination rate
    if any("n_toolcalls" in r for r in report.values()):
        n_hallucinations = sum(
            r.get("n_tool_hallucinations", 0) for r in report.values()
        )
        n_toolcalls = sum(r.get("n_toolcalls", 0) for r in report.values())
        metrics["tool_hallucination_rate"] = (
            n_hallucinations / n_toolcalls if n_toolcalls > 0 else 0
        )

    return metrics


class Evaluation:
    """Runs benchmark evaluations across agents and tasklists.

    Orchestrates the evaluation loop: loads tasks, dispatches them to agents,
    verifies answers, runs analyzers, computes metrics, and writes JSONL results.

    Args:
        name: Run name used for the output JSONL filename.
        task_amount_limit: Maximum number of tasks to evaluate per tasklist.
            None means evaluate all tasks.
        runs_per_configuration: Number of evaluation runs per agent/tasklist pair.
        output_path: Directory for JSONL result files. Defaults to ~/.cache/palace/results/.
        on_task_complete: Optional callback invoked after each task with (current, total).
        enable_citation_verifier: Enable the citation verifier analyzer.
            None falls back to the ENABLE_CITATION_VERIFIER env var.
        io_adapter: Optional model I/O adapter config dict for specialized models.
        report_detail: Level of detail in per-task report. ``"none"`` omits
            ``detailed_report`` entirely, ``"default"`` includes it without
            ``objective``/``expected`` fields, ``"full"`` includes everything.
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
    ):
        if report_detail not in ("none", "default", "full"):
            raise ValueError(
                f"report_detail must be 'none', 'default', or 'full', got '{report_detail}'"
            )
        self.name = name
        self.task_amount_limit = task_amount_limit
        self.runs_per_configuration = runs_per_configuration
        self.output_path = output_path or RESULTS_PATH
        self.on_task_complete = on_task_complete
        self.io_adapter = io_adapter
        self.report_detail = report_detail

        # Initialize analyzers based on toggles
        self.analyzers = []

        # Resolve citation verifier toggle: param overrides env var
        if enable_citation_verifier is None:
            enable_citation_verifier = os.getenv(
                "ENABLE_CITATION_VERIFIER", ""
            ).lower() in ("true", "1", "yes")

        if enable_citation_verifier:
            self.analyzers.append(CitationVerifier(fetch_fn=get_fetch_fn()))

    def _run_analyzers(
        self,
        task: Task,
        answer: str,
        verification_result: TaskVerificationResult,
    ) -> dict[str, Any]:
        """Run applicable analyzers and return metrics.

        Args:
            task: The task that was evaluated
            answer: The agent's answer
            verification_result: Result from task.verify()

        Returns:
            Dict of analyzer metrics keyed by analyzer name
        """
        analyzer_metrics = {}
        for analyzer in self.analyzers:
            # Skip if analyzer doesn't support this task type
            if type(task) not in analyzer.supported_task_types:
                continue
            try:
                with loading() as ld:
                    ld.description = f"Running {analyzer.name}..."
                    metrics = analyzer.analyze(task, answer, verification_result)
                analyzer_metrics[analyzer.name] = metrics
                print(
                    analyzer.format_summary(metrics),
                    box=True,
                    box_title=f":mag: {analyzer.name}",
                )
            except Exception as e:
                print(f"[bold red]Analyzer {analyzer.name} failed: {e}[/]")
                analyzer_metrics[analyzer.name] = {"error": str(e)}
        return analyzer_metrics

    def evaluate_all(
        self,
        agents: list[Agent],
        tasklists: list[str],
    ):
        """Run evaluations for all agent/tasklist combinations.

        Iterates over the cartesian product of agents and tasklists,
        running each pair for ``runs_per_configuration`` iterations.
        Results are appended to a JSONL file and returned as a DataFrame.

        Args:
            agents: List of agents to evaluate.
            tasklists: List of tasklist names to evaluate on.

        Returns:
            DataFrame with one row per run containing accuracy, metrics,
            and detailed report.
        """
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

                # Task-type aggregation (F1, avg_normalized_score, etc.)
                task_type_metrics = task_cls.aggregate(verification_results)
                accuracy = task_type_metrics.pop("accuracy", 0)

                # Agent-execution metrics (pass@k, averages, tool hallucination)
                evaluated_report = {
                    k: v for k, v in report.items() if not v.get("is_skipped")
                }
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

                # Build metrics dict with standardized structure
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

                # append results to jsonl file
                os.makedirs(self.output_path, exist_ok=True)
                with open(
                    self.output_path / f"{self.name}.jsonl",
                    "a",
                    encoding="utf-8",
                ) as f:
                    run_json = json.dumps(run_results, ensure_ascii=False)
                    f.write(run_json + "\n")

        return pd.DataFrame(results)

    def evaluate(
        self,
        agent: Agent,
        tasklist: str,
    ) -> tuple[dict[str, dict], list[TaskVerificationResult], type[Task]]:
        """Evaluate a single agent on a single tasklist.

        Loads tasks from the tasklist directory, runs each through the agent,
        verifies answers, and collects metrics.

        Args:
            agent: The agent to evaluate.
            tasklist: Name of the tasklist directory under the tasklists path.

        Returns:
            Tuple of (report dict mapping task ID to result dict,
            list of verification results, task class used).
        """
        report: dict[str, dict] = {}
        verification_results: list[TaskVerificationResult] = []
        tasklist_path = TASKLISTS_PATH / tasklist

        # Validate tasklist exists
        if not tasklist_path.exists():
            available = [t.name for t in TASKLISTS_PATH.iterdir() if t.is_dir()]
            raise FileNotFoundError(
                f"Tasklist '{tasklist}' not found. "
                f"Available tasklists: {', '.join(sorted(available)) if available else 'none (run palace-download first)'}. "
                f"Note: tasklist names are case-sensitive."
            )

        # load tasklist and metadata
        with open(tasklist_path / "info.json") as f:
            tasklist_info = json.load(f)

        # Resolve task class for aggregation
        from palace.task_types.agentic import AgenticTask
        from palace.task_types.classification import ClassificationTask
        from palace.task_types.qa import QATask
        from palace.task_types.report_generation import ReportGenerationTask

        task_type_map = {
            "QA": QATask,
            "Classification": ClassificationTask,
            "Report Generation": ReportGenerationTask,
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
                    "Install with: pip install palace[agentic]  "
                    "(or: uv run --extra agentic)"
                )
            if not isinstance(agent, VivariumAgent):
                agent = VivariumAgent(
                    name=agent.name,
                    url=getattr(agent, "url", ""),
                    token=getattr(agent, "token", None),
                )

        agent.on_tasklist_start(tasklist_path, tasklist_info)

        with open(tasklist_path / "tasks.json") as f:
            json_tasks = json.load(f)
        tasks: list[Task] = [
            Task.from_dict(
                task
                | {
                    "task_type": tasklist_info["task_type"],
                    "task_type_fields": tasklist_info.get("task_type_fields", {})
                    | task.get("task_type_fields", {}),
                }
            )
            for task in json_tasks
        ]

        # limit the number of tasks to evaluate
        if self.task_amount_limit is not None:
            tasks = tasks[: self.task_amount_limit]

        # Resolve model adapter (programmatic > user file > bundled > none)
        file_io_adapters = load_io_adapters()
        bundled_io_adapters = load_io_adapters(BUNDLED_IO_ADAPTERS_FILE)
        result = get_io_adapter(
            agent.name, self.io_adapter, file_io_adapters, bundled_io_adapters
        )
        if result is not None:
            adapter, source = result
            print(f"[blue]:wrench: Using I/O adapter for {agent.name} ({source})[/]")
        else:
            adapter = None

        loop_start_time = time.time()
        status = PersistentStatus()
        status.start()
        try:
            for i, task in enumerate(tasks):
                agent.on_task_start(task)
                task_metrics = {}  # Initialize before conditional branches
                verification_result = None  # Initialize for analyzer check
                image_path = None  # For multimodal tasks
                attachment_content = ""  # Raw text attachment content for adapter
                is_skipped = False
                skip_reason = None

                if task.attachment is not None and task.attachment != "":
                    attachment_file = tasklist_path / "task_files" / task.attachment

                    # Check if attachment is an image
                    if is_image_attachment(task.attachment):
                        image_path = str(attachment_file)
                        attachment_str = ""
                        attachment_str_debug = f"[Image: {task.attachment}]\n\n"
                    else:
                        # Try to read as text attachment
                        try:
                            with open(attachment_file, encoding="utf-8") as f:
                                attachment_content = f.read()
                        except UnicodeDecodeError:
                            print(
                                f"[yellow bold]Skipping task {task.id}: unsupported attachment type '{task.attachment}' (not text or image)[/]"
                            )
                            vr = TaskVerificationResult(
                                is_correct=False,
                                is_skipped=True,
                                skip_reason="unsupported_attachment",
                            )
                            verification_results.append(vr)
                            report[task.id] = {
                                "actual": None,
                                "is_correct": False,
                                "is_skipped": True,
                                "skip_reason": "unsupported_attachment",
                                "reasoning": None,
                                "elapsed_time": 0.0,
                            }
                            if self.report_detail == "full":
                                report[task.id]["objective"] = task.objective
                                report[task.id]["expected"] = task.expected_display()
                            self.on_task_complete(
                                i + 1, len(tasks)
                            ) if self.on_task_complete is not None else None
                            agent.on_task_end(task)
                            continue

                        max_attachment_len = 200000
                        if len(attachment_content) > max_attachment_len:
                            print(
                                f"[yellow bold]*** DEBUG *** Attachment is too long ({len(attachment_content)}), truncating it to {max_attachment_len} characters."
                            )
                            attachment_content = attachment_content[:max_attachment_len]

                        attachment_str = f"Start of text attachment >>>\n{attachment_content}\n<<< End of text attachment\n\n"
                        attachment_str_debug = f"""Start of text attachment >>>\n{
                            f"{attachment_content[:1000]}... (truncated)"
                            if len(attachment_content) > 1000
                            else attachment_content
                        }\n<<< End of text attachment\n\n"""
                else:
                    attachment_str = ""
                    attachment_str_debug = ""

                # Build prompt: adapter overrides default prompt construction
                if adapter is not None:
                    prompt = adapter.adapt_input(task, attachment_content)
                    agent_prompt = prompt  # No separate attachment wrapping
                else:
                    prompt = task.create_prompt()
                    agent_prompt = f"{attachment_str}{prompt}"

                print()
                print(
                    f"{attachment_str_debug}{prompt}",
                    box=True,
                    box_title=f":memo: Task {i + 1}/{len(tasks)}",
                )
                if task.expected_display() is not None:
                    print(
                        task.expected_display(),
                        box=True,
                        box_title=":fleur_de_lis: Expected Answer",
                    )

                start_time = time.time()

                # Update persistent status bar
                if i > 0:
                    correct = sum(1 for r in verification_results if r.is_correct)
                    skipped_count = sum(1 for r in verification_results if r.is_skipped)
                    failed = i - correct - skipped_count
                    elapsed = time.time() - loop_start_time
                    eta = elapsed / i * (len(tasks) - i)
                    eta_str = (
                        f"{int(eta // 60)}m {int(eta % 60)}s"
                        if eta >= 60
                        else f"{int(eta)}s"
                    )
                    pct = i / len(tasks)
                    filled = int(pct * 20)
                    bar = "█" * filled + "░" * (20 - filled)
                    status.update(
                        f"{bar} {i}/{len(tasks)} | ✓ {correct} ✗ {failed} ⏭ {skipped_count} | ETA: {eta_str}"
                    )
                else:
                    status.update(f"{'░' * 20} 0/{len(tasks)}")

                # Run agent with error handling
                try:
                    with loading() as ld:
                        ld.description = "Agent generating response..."
                        result, run_stats = agent.run(
                            prompt=agent_prompt, image=image_path
                        )
                except ConvergenceError:
                    print(
                        "[bold yellow]:next_track_button: Agent did not converge (max steps reached)[/]"
                    )
                    result, run_stats = None, None
                    skip_reason = "no_response"
                except Exception as e:
                    print(f"[bold yellow]:next_track_button: Agent error: {e}[/]")
                    result, run_stats = None, None
                    skip_reason = "agent_error"

                # Apply output adapter if configured
                if result is not None and adapter is not None:
                    result = adapter.adapt_output(result)

                # check if run completed successfully
                if result is None:
                    print(
                        "[bold yellow]:next_track_button: Task skipped — the agent didn't provide a response.[/]"
                    )
                    is_correct = False
                    reasoning = None
                    is_skipped = True
                    skip_reason = skip_reason or "no_response"
                    verification_results.append(
                        TaskVerificationResult(
                            is_correct=False,
                            is_skipped=True,
                            skip_reason=skip_reason,
                        )
                    )
                elif (
                    task.custom_verificator is not None
                    and task.custom_verificator != ""
                ):

                    def load_function(code: str):
                        # Create an isolated namespace for the exec
                        local_env = {}
                        exec(code, {}, local_env)
                        return local_env["verify"]

                    try:
                        verificator = load_function(task.custom_verificator)
                        is_correct = verificator(result, task.expected)
                        reasoning = None
                        verification_results.append(
                            TaskVerificationResult(
                                is_correct=is_correct, reasoning=reasoning
                            )
                        )
                    except Exception as e:
                        print(
                            f"[bold red]There was an issue verifying the agent response with the custom verificator.\nThe verificator is:\n{task.custom_verificator}\nThe exception is:\n{e}.\nSkipping to next task.[/]"
                        )
                        is_correct = False
                        reasoning = None
                        is_skipped = True
                        skip_reason = "custom_verificator_error"
                        verification_results.append(
                            TaskVerificationResult(
                                is_correct=False,
                                is_skipped=True,
                                skip_reason="custom_verificator_error",
                            )
                        )
                else:
                    print(
                        result, box=True, box_title=":left_speech_bubble: Agent Answer"
                    )

                    try:
                        with loading() as ld:
                            ld.description = "Verifying answer..."
                            verification_result = task.verify(result)

                        # Handle both tuple (legacy) and TaskVerificationResult
                        if isinstance(verification_result, TaskVerificationResult):
                            is_correct = verification_result.is_correct
                            reasoning = verification_result.reasoning
                            task_metrics = verification_result.metrics
                            verification_results.append(verification_result)
                        else:
                            print(
                                f"[bold yellow]Legacy verification result format detected for task type {type(task).__name__}. Consider updating the task.verify() method to return a TaskVerificationResult for richer metrics and reasoning.[/]"
                            )
                            is_correct, reasoning = verification_result
                            verification_results.append(
                                TaskVerificationResult(
                                    is_correct=is_correct, reasoning=reasoning
                                )
                            )

                        if is_correct:
                            print("[bold green]:white_check_mark: Correct[/]")
                        else:
                            print("[bold red]:cross_mark: Incorrect[/]")
                        if reasoning is not None:
                            print(reasoning, box=True, box_title=":judge: Reasoning")
                    except Exception as e:
                        print(
                            f"[bold yellow]:next_track_button: Verification error: {e}[/]"
                        )
                        is_correct = False
                        reasoning = None
                        is_skipped = True
                        skip_reason = "verification_error"
                        verification_results.append(
                            TaskVerificationResult(
                                is_correct=False,
                                is_skipped=True,
                                skip_reason="verification_error",
                            )
                        )

                # prepare report
                elapsed_time = round(time.time() - start_time, 2)
                report[task.id] = {
                    "actual": result,
                    "is_correct": is_correct if result is not None else False,
                    "is_skipped": is_skipped,
                    "skip_reason": skip_reason,
                    "reasoning": reasoning,
                    "elapsed_time": elapsed_time,
                }
                if self.report_detail == "full":
                    report[task.id]["objective"] = task.objective
                    report[task.id]["expected"] = task.expected_display()

                # Add task-type-specific metrics to report
                if task_metrics:
                    report[task.id]["metrics"] = task_metrics

                # Run analyzers and add their metrics
                if (
                    result is not None
                    and not is_skipped
                    and isinstance(verification_result, TaskVerificationResult)
                ):
                    analyzer_metrics = self._run_analyzers(
                        task, result, verification_result
                    )
                    if analyzer_metrics:
                        if "metrics" not in report[task.id]:
                            report[task.id]["metrics"] = {}
                        report[task.id]["metrics"]["analyzers"] = analyzer_metrics

                # add agent execution metrics to report
                if run_stats is not None:
                    for k, v in run_stats.items():
                        report[task.id][k] = v

                # call the on_task_complete callback, if provided
                self.on_task_complete(
                    i + 1, len(tasks)
                ) if self.on_task_complete is not None else None

                agent.on_task_end(task)
        finally:
            status.stop()

        agent.on_tasklist_end()
        return report, verification_results, task_cls
