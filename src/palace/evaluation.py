import itertools
import json
import os
import re
import time
from typing import Optional

import pandas as pd

from palace.agents import Agent
from palace.models import HuggingfaceModel, OpenAICompatibleModel
from palace.utils.paths import PROJECT_ROOT
from palace.utils.printing import loading, print


class Evaluation:
    def __init__(
        self,
        name: str = "eval",
        judge_inference: str = "remote",  # "local" for HuggingfaceModel or "remote" for OpenAICompatibleModel
        task_amount_limit: Optional[int] = None,
        runs_per_configuration: int = 1,
        text_tasks_only: bool = True,
    ):
        self.name = name
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
        self.judge_prompt = """You will be given a question, the correct answer, and another answer provided by the user, with this exact template:

QUESTION
The question

CORRECT ANSWER
The correct answer

PROVIDED ANSWER
The provided answer

Your job is to assess whether the provided answer is a correct answer to the question, using the "correct" answer as a reference. You have to understand from the question if it requires a strict answer or if it allows for a somewhat more open / generic answer. For example, if the question asks for a specific word to be found in a specific place, it probably requires an exact match, while if the question asks for a recipe, or a general sentence, or abstract information, maybe the two answers don't need to match exactly, as long as the semantic content is correct. Just use your best judgement and try your best, as if you were the evaluator and had to grade these assignments as correct or incorrect.
Your output must follow this format:

REASONING
Your observations and reasoning about why the provided answer might or might not be correct. Please be detailed. From this paragraph it should be obvious why you decided to give a correct or incorrect score.

JUDGEMENT
Either Correct or Incorrect. No other text can be here.
"""

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
                pass_at_k_metrics_names = [
                    {"name": "n_steps", "symbol": "s"},
                    {"name": "n_toolcalls", "symbol": "tc"},
                ]
                k_values = [1, 3, 6, 10]

                for metric, k_value in itertools.product(
                    pass_at_k_metrics_names, k_values
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
                    pass_at_k_scores[f"pass@{k_value}{metric['symbol']}"] = (
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
                for metric in pass_at_k_metrics_names:
                    total = 0
                    count = 0
                    total_passed = 0
                    count_passed = 0
                    total_failed = 0
                    count_failed = 0
                    for task_report in report.values():
                        if metric["name"] not in task_report:
                            continue
                        total += task_report[metric["name"]]
                        count += 1
                        if task_report["is_correct"]:
                            total_passed += task_report[metric["name"]]
                            count_passed += 1
                        elif not task_report["is_correct"]:
                            total_failed += task_report[metric["name"]]
                            count_failed += 1
                        else:
                            raise Exception("Task is neither correct nor not correct")
                    if count > 0:
                        metrics_averages[f"avg_{metric['name']}"] = total / count
                    if count_passed > 0:
                        metrics_averages[f"avg_{metric['name']}_passed"] = (
                            total_passed / count_passed
                        )
                    if count_failed > 0:
                        metrics_averages[f"avg_{metric['name']}_failed"] = (
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
                    tool_hallucination_rate = {
                        "tool_hallucination_rate": sum(
                            [
                                task_report.get("n_tool_hallucinations", 0)
                                for task_report in report.values()
                            ]
                        )
                        / sum(
                            [
                                task_report.get("n_toolcalls", 0)
                                for task_report in report.values()
                            ]
                        )
                    }

                print()
                print(
                    f"[blue]:robot: {agent.name} ({agent.model_name} x {agent.paradigm_name})[/]:\n"
                    + f"on :package: [blue]{agent.environment.name}[/]\n"
                    + f"on :scroll: [blue]{tasklist}[/]\n\n"
                    + f"[blue]{correct_tasks}[/] / [blue]{len(report)}[/] ([blue]{accuracy * 100:.0f}%[/])[/] tasks completely successfully.\n"
                    + f"Total time: [blue]{total_time}[/]",
                    box=True,
                    box_title="Evaluation report:",
                )

                run_results = {
                    "agent": agent.name,
                    "model": agent.model_name,
                    "paradigm": agent.paradigm_name,
                    "environment": agent.environment.name,
                    "tasklist": tasklist,
                    "accuracy": accuracy,
                    "total_time": total_time,
                    "detailed_report": report,
                }
                run_results |= pass_at_k_scores
                run_results |= metrics_averages
                run_results |= tool_hallucination_rate
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
        report: dict[str, dict] = {}

        # load tasklist and metadata
        with open(
            PROJECT_ROOT / "tasklists" / "metadata" / tasklist / "info.json"
        ) as f:
            tasklist_info = json.load(f)

        tasklist_path = (
            PROJECT_ROOT
            / "tasklists"
            / ("automated" if tasklist_info["type"] == "automated" else "custom")
            / tasklist
        )
        with open(tasklist_path / "tasks.json") as f:
            tasks = json.load(f)

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

            if task["attachment"] is not None and task["attachment"] != "":
                with open(
                    tasklist_path / "task_files" / task["attachment"],
                    encoding="utf-8",
                ) as f:
                    attachment = f.read()
                max_attachment_len = 100000
                if len(attachment) > max_attachment_len:
                    # TODO this is a temporary workaround, it must be fixed. either increase the truncation to the LLM limit or find another way
                    print(
                        f"[yellow bold]*** DEBUG *** Attachment is too long ({len(attachment)}, truncating it to {max_attachment_len})"
                    )
                    attachment = attachment[:max_attachment_len]
                prompt += f"\n\nStart of text attachment >>>\n{attachment}<<< End of text attachment"

            start_time = time.time()
            print()
            print(prompt, box=True, box_title=f":memo: Task {i + 1}")
            print(f"[bold]Expected response:[/] {task['expected']}")

            with loading():
                result = agent.run(task=prompt)

            # check if run completed successfully
            if result is None:
                print(
                    "[bold red]:cross_mark: The agent didn't provide a response. This means it may have reached the maximum number of iterations before providing a final answer, or it may have become stuck in a loop, or (in the case of local agents) it may have forgotten to call the Final Answer Tool.[/]"
                )
                is_correct = False
                judge_reasoning = None
            elif task["custom_verificator"] == "":
                print(f"[bold]Agent response:[/] {result}")

                # run judge model to determine semantic correctness
                conversation = [
                    {"role": "system", "content": self.judge_prompt},
                    {
                        "role": "user",
                        "content": f"""QUESTION
{task["objective"]}

CORRECT ANSWER
{task["expected"]}

PROVIDED ANSWER
{result}""",
                    },
                ]
                judge_output = self.judge.generate(conversation)
                try:
                    judge_reasoning = re.findall(
                        r"REASONING\n(.*?)\nJUDGEMENT", judge_output, flags=re.S
                    )[0]
                except Exception as e:
                    print(
                        f"Couldn't get judge reasoning from judge output:\n{judge_output}\n\nEncountered the following exception: {e}"
                    )
                    judge_reasoning = None
                try:
                    judgement = re.findall(
                        r"JUDGEMENT\n(.*)", judge_output, flags=re.S
                    )[0]
                except Exception as e:
                    print(
                        f"Couldn't get judge judgement from judge output:\n{judge_output}\n\nEncountered the following exception: {e}"
                    )
                    raise e
                # check if judgement is valid (either "Correct" or "Incorrect")
                if judgement == "Correct":
                    is_correct = True
                elif judgement == "Incorrect":
                    is_correct = False
                else:
                    raise ValueError(
                        f"The judge model's judgement can only be Correct or Incorrect. It returned: {judgement}"
                    )
            else:
                # use custom verificator to determine correctness
                try:

                    def load_function(code: str):
                        # Create an isolated namespace for the exec
                        local_env = {}
                        exec(code, {}, local_env)
                        return local_env["verify"]

                    verificator = load_function(task["custom_verificator"])
                    is_correct = verificator(result, task["expected"])
                    judge_reasoning = None
                except Exception as e:
                    print(
                        f"[bold red]There was an issue verifying the agent response with the custom verificator.\nThe verificator is:\n{task['custom_verificator']}\nThe exception is:\n{e}.\nSkipping to next task.[/]"
                    )
                    continue
            if is_correct:
                print("[bold green]:white_check_mark: Correct")
            else:
                print(
                    f"[bold red]:cross_mark: Incorrect[/] (it was [blue]{task['expected']}[/])"
                )
            if judge_reasoning is not None:
                print(f"[italic]Judge Reasoning: {judge_reasoning}[/]")

            # prepare report
            elapsed_time = time.time() - start_time
            report[task["objective"]] = {
                "expected": task["expected"],
                "actual": result if result is not None else "<N/A>",
                "is_correct": is_correct if result is not None else False,  # type: ignore
                "judge_reasoning": judge_reasoning,
                "elapsed_time": elapsed_time,
            }
            # add extra agent execution info to report
            # TODO add telemetry back
            # for k, v in extras.items():
            #     report[task["objective"]][k] = v

        return report

    @staticmethod
    def _task_prompt_prefix(category: str) -> str:
        """Return the task prompt prefix for the given category."""
        if category == "QA":
            return ""  # "Provide the exact answer, without any additional text (for example, if the answer is a name, write only the name as it is):\n"
        elif category == "Claim Verification":
            return "Is the following claim true, false, or we can't say for certain? (Reply with 'True', 'False', or 'Not Enough Info')\n"
        else:
            return ""
