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
from palace.utils.io_adapters import get_io_adapter, load_io_adapters
from palace.utils.multimodal import is_image_attachment
from palace.utils.paths import RESULTS_PATH, TASKLISTS_PATH
from palace.utils.printing import loading, print


def compute_agent_metrics(report: dict[str, dict]) -> dict[str, float]:
    """Compute agent-execution metrics: pass@k, averages, tool hallucination rate."""
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
            len([r for r in report.values() if r["is_correct"] and stat["name"] in r and r[stat["name"]] <= k_value])
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
        n_hallucinations = sum(r.get("n_tool_hallucinations", 0) for r in report.values())
        n_toolcalls = sum(r.get("n_toolcalls", 0) for r in report.values())
        metrics["tool_hallucination_rate"] = n_hallucinations / n_toolcalls if n_toolcalls > 0 else 0

    return metrics


class Evaluation:
    def __init__(
        self,
        name: str = "eval",
        task_amount_limit: int | None = None,
        runs_per_configuration: int = 1,
        output_path: Path | None = None,
        on_task_complete: Callable[[int, int], None] | None = None,
        enable_citation_verifier: bool | None = None,
        io_adapter: dict | None = None,
    ):
        self.name = name
        self.task_amount_limit = task_amount_limit
        self.runs_per_configuration = runs_per_configuration
        self.output_path = output_path or RESULTS_PATH
        self.on_task_complete = on_task_complete
        self.io_adapter = io_adapter

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
                with loading():
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
        results = []

        grid = list(itertools.product(agents, tasklists))
        for agent, tasklist in grid:
            for run in range(self.runs_per_configuration):
                print(f"""
[bold]Evaluating (run [blue]{run + 1}/{self.runs_per_configuration}[/])
:robot: agent [blue] {agent.name}[/]
:package: on enviromnent [blue]{agent.environment.name}[/]
:scroll: on tasklist [blue]{tasklist}[/]
""")

                report, verification_results, task_cls = self.evaluate(agent, tasklist)

                correct_tasks = sum(r.is_correct for r in verification_results)
                total_time = sum(t["elapsed_time"] for t in report.values())

                # Task-type aggregation (F1, avg_normalized_score, etc.)
                task_type_metrics = task_cls.aggregate(verification_results)

                # Agent-execution metrics (pass@k, averages, tool hallucination)
                agent_metrics = compute_agent_metrics(report)

                accuracy = task_type_metrics.get("accuracy", 0)

                print()
                print(
                    f"[blue]:robot: {agent.name} ({agent.model_name} x {agent.paradigm_name})[/]:\n"
                    + f"on :package: [blue]{agent.environment.name}[/]\n"
                    + f"on :scroll: [blue]{tasklist}[/]\n\n"
                    + f"[blue]{correct_tasks}[/] / [blue]{len(report)}[/] ([blue]{accuracy * 100:.0f}%[/])[/] tasks completely successfully.\n"
                    + f"Total time: [blue]{total_time}[/]",
                    box=True,
                    box_title="Evaluation Report",
                )

                # Build metrics dict
                metrics: dict[str, int | float | dict] = {
                    "task_count": len(report),
                    "correct_count": correct_tasks,
                    "total_time": total_time,
                }
                metrics |= task_type_metrics
                metrics |= agent_metrics

                run_results = {
                    "agent": agent.name,
                    "model": agent.model_name,
                    "paradigm": agent.paradigm_name,
                    "environment": agent.environment.name,
                    "tasklist": tasklist,
                    "accuracy": accuracy,
                    "metrics": metrics,
                    "detailed_report": report,
                }
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
        report: dict[str, dict] = {}
        verification_results: list[TaskVerificationResult] = []
        tasklist_path = TASKLISTS_PATH / tasklist

        # load tasklist and metadata
        with open(tasklist_path / "info.json") as f:
            tasklist_info = json.load(f)

        # Resolve task class for aggregation
        from palace.task_types.classification import ClassificationTask
        from palace.task_types.qa import QATask
        from palace.task_types.report_generation import ReportGenerationTask

        task_type_map = {
            "QA": QATask,
            "Classification": ClassificationTask,
            "Report Generation": ReportGenerationTask,
        }
        task_cls = task_type_map.get(tasklist_info["task_type"], Task)

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

        # Resolve model adapter (programmatic > file > none)
        file_io_adapters = load_io_adapters()
        adapter = get_io_adapter(agent.name, self.io_adapter, file_io_adapters)
        if adapter is not None:
            print(f"[blue]:wrench: Using I/O adapter for {agent.name}[/]")

        for i, task in enumerate(tasks):
            task_metrics = {}  # Initialize before conditional branches
            verification_result = None  # Initialize for analyzer check
            image_path = None  # For multimodal tasks
            attachment_content = ""  # Raw text attachment content for adapter

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

            print(
                f"{attachment_str_debug}{prompt}",
                box=True,
                box_title=f":memo: Task {i + 1}",
            )
            print(
                task.expected_display(),
                box=True,
                box_title=":fleur_de_lis: Expected Answer",
            )

            start_time = time.time()
            with loading():
                result, run_stats = agent.run(
                    prompt=agent_prompt, image=image_path
                )

            # Apply output adapter if configured
            if result is not None and adapter is not None:
                result = adapter.adapt_output(result)

            # check if run completed successfully
            if result is None:
                print(
                    "[bold red]:cross_mark: The agent didn't provide a response. This means it may have reached the maximum number of iterations before providing a final answer, or it may have become stuck in a loop, or (in the case of local agents) it may have forgotten to call the Final Answer Tool.[/]"
                )
                is_correct = False
                reasoning = None
                verification_results.append(TaskVerificationResult(is_correct=False, reasoning="No response"))
            elif task.custom_verificator is not None and task.custom_verificator != "":

                def load_function(code: str):
                    # Create an isolated namespace for the exec
                    local_env = {}
                    exec(code, {}, local_env)
                    return local_env["verify"]

                try:
                    verificator = load_function(task.custom_verificator)
                    is_correct = verificator(result, task.expected)
                    reasoning = None
                    verification_results.append(TaskVerificationResult(is_correct=is_correct, reasoning=reasoning))
                except Exception as e:
                    print(
                        f"[bold red]There was an issue verifying the agent response with the custom verificator.\nThe verificator is:\n{task.custom_verificator}\nThe exception is:\n{e}.\nSkipping to next task.[/"
                    )
                    continue
            else:
                print(result, box=True, box_title=":left_speech_bubble: Agent Answer")
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
                    verification_results.append(TaskVerificationResult(is_correct=is_correct, reasoning=reasoning))

                if is_correct:
                    print("[bold green]:white_check_mark: Correct[/]")
                else:
                    print("[bold red]:cross_mark: Incorrect[/]")
                if reasoning is not None:
                    print(reasoning, box=True, box_title=":judge: Reasoning")

            # prepare report
            elapsed_time = time.time() - start_time
            report[task.id] = {
                "objective": task.objective,
                "expected": task.expected_display(),
                "actual": result,
                "is_correct": is_correct if result is not None else False,
                "reasoning": reasoning,
                "elapsed_time": elapsed_time,
            }

            # Add task-type-specific metrics to report
            if task_metrics:
                report[task.id]["metrics"] = task_metrics

            # Run analyzers and add their metrics
            if result is not None and isinstance(
                verification_result, TaskVerificationResult
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

        return report, verification_results, task_cls
