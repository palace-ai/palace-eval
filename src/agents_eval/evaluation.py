import itertools
import json
import os
import time
from typing import Dict, List

import pandas as pd

from agents_eval.agents import Agent
from agents_eval.models import HuggingfaceModel, OpenAICompatibleModel
from agents_eval.utils.paths import PROJECT_ROOT
from agents_eval.utils.printing import loading, print


class Evaluation:
    def __init__(
        self,
        name: str = "eval",
        judge_inference: str = "remote",  # "local" for HuggingfaceModel or "remote" for OpenAICompatibleModel
        verbose: bool = True,
        task_amount_limit: int = None,
        runs_per_configuration: int = 1,
        text_tasks_only: bool = True,
    ):
        self.name = name
        self.verbose = verbose
        self.task_amount_limit = task_amount_limit
        self.runs_per_configuration = runs_per_configuration
        self.text_tasks_only = text_tasks_only

        # initialize judge model
        if judge_inference == "local":
            judge_model_id = "/mnt/storage2/hf_models/Qwen2.5-3B-Instruct"
            self.judge = HuggingfaceModel(judge_model_id, gpu_memory_utilization=0.3)
        elif judge_inference == "remote":
            self.judge = OpenAICompatibleModel("meta-llama/Llama-3.3-70B-Instruct")
        else:
            raise ValueError(
                f"judge_inference must be either 'local' or 'remote', found: {judge_inference}"
            )
        self.judge_prompt = """Your job is to assess whether two responses are semantically equivalent. You will be given a response which was obtained by an AI assistant, and the corresponding ground truth, which is what the user expected to receive from the assistant. You can only reply to each prompt with either "True" or "False", depending on whether you think that the two provided responses are semantically equivalent or not. You can't produce any other symbol other than "True" or "False"."""

    def evaluate_all(
        self,
        agents: List[Agent],
        tasklists: List[str],
        _temperatures: List[float] = [0.0],
    ):
        results = []

        grid = list(itertools.product(agents, tasklists, _temperatures))
        for agent, tasklist, _temperature in grid:
            for run in range(self.runs_per_configuration):
                print(f"""
[bold]Evaluating (run [blue]{run + 1}/{self.runs_per_configuration}[/])
:robot: agent [blue] {agent.name}[/]
:package: on enviromnent [blue]{agent.environment_name}[/]
:scroll: on tasklist [blue]{tasklist}[/]
on _temperature [blue]{_temperature}[/]
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

                print()
                print(
                    f"[blue]{correct_tasks}[/] / [blue]{len(report)}[/] ([blue]{accuracy * 100:.0f}%[/])[/] tasks completely successfully.",
                    box=True,
                    box_title="Evaluation report:",
                )

                run_results = {
                    "agent": agent.name,
                    "model": agent.model_name,
                    "paradigm": agent.paradigm_name,
                    "environment": agent.environment_name,
                    "tasklist": tasklist,
                    "_temperature": _temperature,
                    "accuracy": accuracy,
                    "total_time": total_time,
                    "detailed_report": report,
                }
                results.append(run_results)

                # append results to jsonl file
                os.makedirs(PROJECT_ROOT / "results/", exist_ok=True)
                with open(
                    PROJECT_ROOT / "results" / f"{self.name}.jsonl",
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
        report: Dict[str, bool] = {}

        # load tasklist and metadata
        with open(PROJECT_ROOT / "tasklists" / tasklist / "tasks.json") as f:
            tasks = json.load(f)
        with open(PROJECT_ROOT / "tasklists" / tasklist / "info.json") as f:
            tasklist_info = json.load(f)

        # filter out tasks that are not text-based
        if self.text_tasks_only:
            tasks = [
                task
                for task in tasks
                if task["attachment"] is None
                or task["attachment"] == ""
                or task["attachment"][-4:] == ".txt"
            ]

        # limit the number of tasks to evaluate
        if self.task_amount_limit is not None:
            tasks = tasks[: self.task_amount_limit]

        for i, task in enumerate(tasks):
            # preprocess task according to category
            prompt = (
                __class__._task_prompt_prefix(tasklist_info["category"])
                + task["objective"]
            )
            # task["objective"] = (
            #     __class__._task_prompt_prefix(tasklist_info["category"])
            #     + task["objective"]
            # )

            if task["attachment"] is not None and task["attachment"] != "":
                with open(
                    PROJECT_ROOT
                    / "tasklists"
                    / tasklist
                    / "task_files"
                    / task["attachment"]
                ) as f:
                    attachment = f.read()
                prompt += f"\n\nStart of text attachment >>>\n{attachment}<<< End of text attachment"

            start_time = time.time()
            print()
            print(prompt, box=True, box_title=f":memo: Task {i + 1}")
            print(f"[bold]Expected response:[/] {task['expected']}")

            with loading():
                result = agent.run(task=prompt, verbose=self.verbose)

            # check if run completed successfully
            if result is None:
                print(
                    "[bold red]:cross_mark: The agent didn't provide a response. This means it may have reached the maximum number of iterations before providing a final answer, or it may have become stuck in a loop, or (in the case of local agents) it may have forgotten to call the Final Answer Tool.[/]"
                )
            else:
                print(f"[bold]Agent response:[/] {result}")

                # run judge model to determine semantic correctness
                conversation = [
                    {"role": "system", "content": self.judge_prompt},
                    {
                        "role": "user",
                        "content": f"""AI assistant response: {result}
        Expected response: {task["expected"]}""",
                    },
                ]
                verdict = self.judge.generate(conversation)

                # check if verdict is valid (either "True" or "False")
                if verdict == "True":
                    is_correct = True
                elif verdict == "False":
                    is_correct = False
                else:
                    raise ValueError(
                        f"The judge model can only return True or False. It returned: {verdict}"
                    )

                if is_correct:
                    print("[bold green]:white_check_mark: Correct")
                else:
                    print(
                        f"[bold red]:cross_mark: Incorrect[/] (it was [blue]{task['expected']}[/])"
                    )

            # prepare report
            elapsed_time = time.time() - start_time
            report[task["objective"]] = {
                "expected": task["expected"],
                "actual": result if result is not None else "N/A",
                "is_correct": is_correct if result is not None else False,
                "elapsed_time": elapsed_time,
            }

        return report

    def _task_prompt_prefix(category: str) -> str:
        """Return the task prompt prefix for the given category."""
        if category == "QA":
            return "Provide the exact answer, without any additional text (for example, if the answer is a name, write only the name as it is):\n"
        elif category == "Claim Verification":
            return "Is the following claim true, false, or we can't say for certain? (Reply with 'True', 'False', or 'Not Enough Info')\n"
        else:
            raise ValueError(f"Unknown category: {category}")
