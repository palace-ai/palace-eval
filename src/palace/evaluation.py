import itertools
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

from palace.agents import Agent
from palace.analyzers import CitationVerifier
from palace.analyzers.fetch import get_fetch_fn
from palace.task_types import Task, TaskVerificationResult
from palace.utils.paths import RESULTS_PATH, TASKLISTS_PATH
from palace.utils.printing import loading, print

agent_run_stats: list[dict[str, Any]] = [
    {"name": "n_steps", "pass@k": True, "pass@k_symbol": "s"},
    {"name": "n_toolcalls", "pass@k": True, "pass@k_symbol": "tc"},
    {"name": "n_tool_hallucinations"},
    {"name": "tools_list"},
    {"name": "tool_calls_list"},
]


class Evaluation:
    def __init__(
        self,
        name: str = "eval",
        task_amount_limit: Optional[int] = None,
        runs_per_configuration: int = 1,
        text_tasks_only: bool = True,
        output_path: Path | None = None,
        on_task_complete: Callable[[int, int], None] | None = None,
        enable_citation_verifier: Optional[bool] = None,
    ):
        self.name = name
        self.task_amount_limit = task_amount_limit
        self.runs_per_configuration = runs_per_configuration
        self.text_tasks_only = text_tasks_only
        self.output_path = output_path or RESULTS_PATH
        self.on_task_complete = on_task_complete

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
            if type(task.task_type) not in analyzer.supported_task_types:
                continue
            try:
                with loading():
                    metrics = analyzer.analyze(task, answer, verification_result)
                analyzer_metrics[analyzer.name] = metrics
                print(analyzer.format_summary(metrics), box=True, box_title=f":mag: {analyzer.name}")
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

                report = self.evaluate(agent, tasklist)

                # aggregate relevant information from individual tasklist
                correct_tasks = sum(
                    [task_report["is_correct"] for _, task_report in report.items()]
                )
                total_time = sum(
                    [task_report["elapsed_time"] for _, task_report in report.items()]
                )
                accuracy = (correct_tasks / len(report)) if correct_tasks > 0 else 0

                # compute pass@k scores
                # pass@{N}{metric} is the probability of completing a given task successfully by using not more than N metric
                # the score is not based only on passed tasks but on failed tasks too! (they will decrease the final score)
                # basically, any pass@{N}{metric} score can never be greater than the accuracy; it's just accuracy with extra constraints
                pass_at_k_scores = {}
                for metric, k_value in itertools.product(
                    [
                        stat
                        for stat in agent_run_stats
                        if stat.get("pass@k") and stat["name"] in report
                    ],
                    [1, 3, 6, 10],
                ):
                    n_tasks_with_metric = len(
                        [
                            task_report
                            for task_report in report.values()
                            if metric["name"] in task_report
                        ]
                    )
                    if n_tasks_with_metric == 0:
                        continue  # skip to avoid division by zero
                    pass_at_k_scores[f"pass@{k_value}{metric['pass@k_symbol']}"] = (
                        len(
                            [
                                task_report
                                for task_report in report.values()
                                if task_report["is_correct"]
                                and metric["name"] in task_report
                                and task_report[metric["name"]] <= k_value
                            ]
                        )
                        / n_tasks_with_metric
                    )

                # compute averages for each task-specific metric, including average when the task is successful and average when the task failed
                metrics_averages = {}
                for stat in agent_run_stats:
                    if not stat.get("pass@k") or stat["name"] not in report:
                        continue
                    total = 0
                    count = 0
                    total_passed = 0
                    count_passed = 0
                    total_failed = 0
                    count_failed = 0
                    for task_report in report.values():
                        total += task_report[stat["name"]]
                        count += 1
                        if task_report["is_correct"]:
                            total_passed += task_report[stat["name"]]
                            count_passed += 1
                        elif not task_report["is_correct"]:
                            total_failed += task_report[stat["name"]]
                            count_failed += 1
                        else:
                            raise Exception("Task is neither correct nor not correct")
                    if count > 0:
                        metrics_averages[f"avg_{stat['name']}"] = total / count
                    if count_passed > 0:
                        metrics_averages[f"avg_{stat['name']}_passed"] = (
                            total_passed / count_passed
                        )
                    if count_failed > 0:
                        metrics_averages[f"avg_{stat['name']}_failed"] = (
                            total_failed / count_failed
                        )

                # compute tool hallucination rate: total number of tool hallucinations over total number of tool calls
                tool_hallucination_rate = {}
                if (  # if there is at least one task with number of toolcalls recorded (to avoid divion by zero)
                    len(
                        [
                            task_report
                            for task_report in report.values()
                            if "n_toolcalls" in task_report
                        ]
                    )
                    > 0
                ):
                    n_tool_hallucinations = sum(
                        [
                            task_report.get("n_tool_hallucinations", 0)
                            for task_report in report.values()
                        ]
                    )
                    n_toolcalls = sum(
                        [
                            task_report.get("n_toolcalls", 0)
                            for task_report in report.values()
                        ]
                    )
                    tool_hallucination_rate = {
                        "tool_hallucination_rate": n_tool_hallucinations / n_toolcalls
                        if n_toolcalls > 0
                        else 0
                    }

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

                # Build metrics dict with universal metrics
                metrics: dict[str, int | float | dict] = {
                    "task_count": len(report),
                    "correct_count": correct_tasks,
                    "total_time": total_time,
                }
                metrics |= pass_at_k_scores
                metrics |= metrics_averages
                if tool_hallucination_rate:
                    metrics |= tool_hallucination_rate

                # Aggregate task-type-specific metrics (e.g., avg normalized_score for ReportGeneration)
                task_type_metrics = {}
                normalized_scores = [
                    r["metrics"]["normalized_score"]
                    for r in report.values()
                    if r.get("metrics") and "normalized_score" in r["metrics"]
                ]
                if normalized_scores:
                    task_type_metrics["avg_normalized_score"] = sum(normalized_scores) / len(normalized_scores)
                if task_type_metrics:
                    metrics["task_type_metrics"] = task_type_metrics

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
    ):
        report: dict[str, dict] = {}
        tasklist_path = TASKLISTS_PATH / tasklist

        # load tasklist and metadata
        with open(tasklist_path / "info.json") as f:
            tasklist_info = json.load(f)

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

        # filter out tasks that are not text-based
        if self.text_tasks_only:
            tasks = [
                task
                for task in tasks
                if task.attachment is None
                or task.attachment == ""
                or task.attachment[-4:] == ".txt"
            ]

        # limit the number of tasks to evaluate
        if self.task_amount_limit is not None:
            tasks = tasks[: self.task_amount_limit]

        for i, task in enumerate(tasks):
            task_metrics = {}  # Initialize before conditional branches
            verification_result = None  # Initialize for analyzer check
            prompt = task.create_prompt()

            if task.attachment is not None and task.attachment != "":
                with open(
                    tasklist_path / "task_files" / task.attachment,
                    encoding="utf-8",
                ) as f:
                    attachment = f.read()
                max_attachment_len = 1000000
                if len(attachment) > max_attachment_len:
                    # TODO this is a temporary workaround, it must be fixed. either increase the truncation to the LLM limit or find another way
                    print(
                        f"[yellow bold]*** DEBUG *** Attachment is too long ({len(attachment)}), truncating it to {max_attachment_len} characters."
                    )
                    attachment = attachment[:max_attachment_len]

                attachment_str = f"Start of text attachment >>>\n{attachment}\n<<< End of text attachment\n\n"
                attachment_str_debug = f"""Start of text attachment >>>\n{
                    f"{attachment[:1000]}... (truncated)"
                    if len(attachment) > 1000
                    else attachment
                }\n<<< End of text attachment\n\n"""
            else:
                attachment_str = ""
                attachment_str_debug = ""

            print(
                f"{attachment_str_debug}{prompt}",
                box=True,
                box_title=f":memo: Task {i + 1}",
            )
            print(task.expected, box=True, box_title=":fleur_de_lis: Expected Answer")

            start_time = time.time()
            with loading():
                result, run_stats = agent.run(task=f"{attachment_str}{prompt}")

            # check if run completed successfully
            if result is None:
                print(
                    "[bold red]:cross_mark: The agent didn't provide a response. This means it may have reached the maximum number of iterations before providing a final answer, or it may have become stuck in a loop, or (in the case of local agents) it may have forgotten to call the Final Answer Tool.[/]"
                )
                is_correct = False
                reasoning = None
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
                else:
                    print(
                        f"[bold yellow]Legacy verification result format detected for task type {type(task).__name__}. Consider updating the task.verify() method to return a TaskVerificationResult for richer metrics and reasoning.[/]"
                    )
                    is_correct, reasoning = verification_result

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
                "expected": task.expected,
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

        return report
