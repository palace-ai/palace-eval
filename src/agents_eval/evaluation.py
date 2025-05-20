import json
import os
import time
from typing import Dict, List

import pandas as pd
from rich import print

from agents_eval.agent import Agent
from agents_eval.environments import Environment
from agents_eval.models import GPTJRCModel, HuggingfaceModel, Model
from agents_eval.paradigms import Paradigm
from agents_eval.utils.paths import PROJECT_ROOT


class Evaluation:
    def __init__(
        self,
        name: str = "eval",
        judge_inference: str = "remote",  # "local" for HuggingfaceModel or "remote" for GPTJRCModel,
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
            self.judge = GPTJRCModel()
        else:
            raise ValueError(
                f"judge_inference must be either 'local' or 'remote', found: {judge_inference}"
            )
        self.judge_prompt = """Your job is to assess whether two responses are semantically equivalent. You will be given a response which was obtained by an AI assistant, and the corresponding ground truth, which is what the user expected to receive from the assistant. You can only reply to each prompt with either "True" or "False", depending on whether you think that the two provided responses are semantically equivalent or not. You can't produce any other symbol other than "True" or "False"."""

    def evaluate_all(
        self,
        models: List[Model],
        paradigms: List[Paradigm],
        environments: List[Environment],
        tasklist: str,
        _temperatures: List[float] = [0.0],
    ):
        results = []

        for model in models:
            for paradigm in paradigms:
                for _temperature in _temperatures:
                    agent = Agent(
                        model, paradigm, _temperature=_temperature, verbose=self.verbose
                    )
                    for environment in environments:
                        for run in range(self.runs_per_configuration):
                            print(f"""\n[bold]Evaluating (run [sky_blue2]{run + 1}/{self.runs_per_configuration}[/])
            :robot: agent [sky_blue2]( {model.name} × {paradigm.name} )[/]
            :package: on enviromnent [sky_blue2]{environment.name}[/]
            :scroll: on tasklist [sky_blue2]{tasklist}[/]
            on _temperature [sky_blue2]{_temperature}[/]""")

                            report = self.evaluate(agent, environment, tasklist)
                            print(report)

                            # aggregate relevant information from individual tasklist
                            correct_tasks = sum(
                                [
                                    task_report["is_correct"]
                                    for _, task_report in report.items()
                                ]
                            )
                            total_time = sum(
                                [
                                    task_report["elapsed_time"]
                                    for _, task_report in report.items()
                                ]
                            )
                            print(f"""\n[bold]Evaluation report:
            {correct_tasks}/{len(report)} ({correct_tasks / len(report) * 100:.0f}%)[/] tasks completely successfully.
            """)

                            # place value (correct_tasks / len(report)) into overall_report in "accuracy" column at the correct row
                            run_results = {
                                "model": model.name,
                                "paradigm": paradigm.name,
                                "environment": environment.name,
                                "tasklist": tasklist,
                                "_temperature": _temperature,
                                "accuracy": correct_tasks / len(report),
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
        environment: Environment,
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
                if task["attachment"] is None or task["attachment"] == ""
            ]

        # limit the number of tasks to evaluate
        if self.task_amount_limit is not None:
            tasks = tasks[: self.task_amount_limit]

        for i, task in enumerate(tasks):
            # preprocess task according to category
            task["objective"] = (
                __class__._task_prompt_prefix(tasklist_info["category"])
                + task["objective"]
            )

            start_time = time.time()
            print(f"""
[bold]:memo: Task {i + 1}
    Objective:[/] {task["objective"]} [bold]
    Expected response:[/] {task["expected"]}""")
            result = agent.run(
                environment=environment,
                task=task["objective"],
            )

            # check if run completed successfully
            if result is None:
                print(
                    "    [bold red]:cross_mark: The agent didn't provide a response. This means either it didn't call the Final Answer tool correctly, or it reached maximum iterations before providing a final answer."
                )
                continue
            else:
                print(f"    [bold]Agent response:[/] {result}")

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
                correct = True
            elif verdict == "False":
                correct = False
            else:
                raise ValueError(
                    f"The judge model can only return True or False. It returned: {verdict}"
                )

            if correct:
                print("    [bold green]:white_check_mark: Correct")
            else:
                print(
                    f"    [bold red]:cross_mark: Incorrect[/] (it was [sky_blue2]{task['expected']}[/])"
                )

            # prepare report
            elapsed_time = time.time() - start_time
            report[task["objective"]] = {
                "expected": task["expected"],
                "actual": result,
                "is_correct": correct,
                "elapsed_time": elapsed_time,
            }

        return report

    def _task_prompt_prefix(category: str) -> str:
        """Return the task prompt prefix for the given category."""
        if category == "QA":
            return ""
        elif category == "Claim Verification":
            return "Is the following claim true, false, or we can't say for certain? (Reply with 'True', 'False', or 'Not Enough Info') \n"
        else:
            raise ValueError(f"Unknown category: {category}")
