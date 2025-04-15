import json
import os
import time
from typing import Dict, List

import pandas as pd
from rich import print

from agent import Agent
from environments import Environment
from models import GPTJRCModel, HuggingfaceModel, Model
from paradigms import Paradigm


class Evaluation:
    def __init__(
        self,
        name: str = "eval",
        judge_inference: str = "remote",  # "local" for HuggingfaceModel or "remote" for GPTJRCModel,
        verbose: bool = True,
        task_amount_limit: int = None,
        runs_per_configuration: int = 1,
    ):
        self.name = name
        self.verbose = verbose
        self.task_amount_limit = task_amount_limit
        self.runs_per_configuration = runs_per_configuration

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
        tasklist: str,  # the name of the tasklist file (without .json extension))
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
                            print(f"""\n[bold]Evaluating (run [sky_blue2]{run}/{self.runs_per_configuration}[/])
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
            {correct_tasks}/{len(self.tasks)} ({correct_tasks / len(self.tasks) * 100:.0f}%)[/] tasks completely successfully.
            """)
                            # place value (correct_tasks / len(self.tasks)) into overall_report in "accuracy" column at the correct row
                            run_results = {
                                "model": model.name,
                                "paradigm": paradigm.name,
                                "environment": environment.name,
                                "tasklist": tasklist,
                                "_temperature": _temperature,
                                "accuracy": correct_tasks / len(self.tasks),
                                "total_time": total_time,
                                "detailed_report": report,
                            }
                            results.append(run_results)

                            # append results to jsonl file
                            os.makedirs("../results/", exist_ok=True)
                            with open(f"../results/{self.name}.jsonl", "a") as f:
                                run_json = json.dumps(run_results)
                                f.write(run_json + "\n")

        return pd.DataFrame(results)

    def evaluate(
        self,
        agent: Agent,
        environment: Environment,
        tasklist: str,
    ):
        report: Dict[str, bool] = {}

        with open(f"../tasklists/{tasklist}.json") as f:
            self.tasks = json.load(f)

        if self.task_amount_limit is not None:
            self.tasks = self.tasks[: self.task_amount_limit]

        for i, task in enumerate(self.tasks):
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


# class Evaluation_old:
#     def __init__(
#         self,
#         models: List[Model],
#         paradigms: List[Paradigm],
#         environments: List[Environment],
#         tasklist: str,  # the name of the tasklist file (without .json extension)
#         judge_inference: str = "remote",  # "local" for HuggingfaceModel or "remote" for GPTJRCModel,
#         verbose: bool = True,
#     ):
#         # save configurations to evaluate
#         self.models = models
#         self.paradigms = paradigms
#         self.environments = environments
#         self.tasklist = tasklist
#         with open(f"../tasklists/{tasklist}.json") as f:
#             self.tasks = json.load(f)
#         self.verbose = verbose

#         # initialize judge model
#         if judge_inference == "local":
#             judge_model_id = "/mnt/storage2/hf_models/Qwen2.5-3B-Instruct"
#             self.judge = HuggingfaceModel(judge_model_id, gpu_memory_utilization=0.3)
#         elif judge_inference == "remote":
#             self.judge = GPTJRCModel()
#         else:
#             raise ValueError(
#                 f"judge_inference must be either 'local' or 'remote', found: {judge_inference}"
#             )
#         self.judge_prompt = """Your job is to assess whether two responses are semantically equivalent. You will be given a response which was obtained by an AI assistant, and the corresponding ground truth, which is what the user expected to receive from the assistant. You can only reply to each prompt with either "True" or "False", depending on whether you think that the two provided responses are semantically equivalent or not. You can't produce any other symbol other than "True" or "False"."""

#     def evaluate_all(self):
#         for model in self.models:
#             agent = None
#             for paradigm in self.paradigms:
#                 agent = Agent(model, paradigm)
#                 for environment in self.environments:
#                     print(f"""\n[bold]Evaluating
#     :robot: agent [sky_blue2]( {model.name} × {paradigm.name} )[/]
#     :package: on enviromnent [sky_blue2]{environment.name}[/]
#     :scroll: on tasklist [sky_blue2]{self.tasklist}[/]""")
#                     correct_tasks: int = 0
#                     for i, task in enumerate(self.tasks):
#                         print(f"""\n[bold]:memo: Task {i + 1}
#     Objective:[/] {task["objective"]} [bold]
#     Expected response:[/] {task["expected"]}""")
#                         result = agent.run(
#                             environment=environment,
#                             task=task["objective"],
#                             verbose=self.verbose,
#                         )

#                         # check if run completed successfully
#                         if result is None:
#                             print(
#                                 "    [bold red]:cross_mark: The agent didn't provide a response. This means either it didn't call the Final Answer tool correctly, or it reached maximum iterations before providing a final answer."
#                             )
#                             continue
#                         else:
#                             print(f"    [bold]Agent response:[/] {result}")

#                         # run judge model to determine semantic correctness
#                         conversation = [
#                             {"role": "system", "content": self.judge_prompt},
#                             {
#                                 "role": "user",
#                                 "content": f"""AI assistant response: {result}
# Expected response: {task["expected"]}""",
#                             },
#                         ]
#                         verdict = self.judge.generate(conversation)

#                         # check if verdict is valid (either "True" or "False")
#                         if verdict == "True":
#                             correct = True
#                         elif verdict == "False":
#                             correct = False
#                         else:
#                             raise ValueError(
#                                 f"The judge model can only return True or False. It returned: {verdict}"
#                             )
#                         correct_tasks += int(correct)
#                         if correct:
#                             print("    [bold green]:white_check_mark: Correct")
#                         else:
#                             print("    [bold red]:cross_mark: Incorrect")
#                     #                     print(
#                     #                         f"""{"\033[1;92m✅" if correct else "\033[1;91m❌"} Task {i + 1}:
#                     # Objective: \033[22m{task["objective"]}\033[1m
#                     # Agent response: \033[22m{result}\033[1m
#                     # Expected response: \033[22m{task["expected"]}\033[0m
#                     # """
#                     #                     )

#                     # print an evaluation report for this configuration
#                     print(f"""\n[bold]Evaluation report:
#     {correct_tasks}/{len(self.tasks)} ({correct_tasks / len(self.tasks) * 100:.0f}%)[/] tasks completely successfully.
#     """)

#             # TODO memory cleanup (Not working)
#             # import gc
#             # import time

#             # import torch

#             # del agent.model.model
#             # agent.del_model()
#             # print("called agent.del_model()")
#             # time.sleep(3)
#             # agent.empty_cuda_cache()
#             # print("called agent.empty_cuda_cache()")
#             # time.sleep(3)
#             # agent.gc()
#             # print("called agent.gc()")
#             # del agent
#             # torch.cuda.empty_cache()
#             # gc.collect()
