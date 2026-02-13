import argparse
import itertools
import json
import random
import re
import shutil
from pathlib import Path
from typing import Optional

import pymupdf
from palace.models.openai_compatible_model import OpenAICompatibleModel
from palace.utils.constants import GPTJRC_PROD_API_URL
from palace.utils.paths import PROJECT_ROOT
from palace.utils.printing import print
from palace.utils.secrets import GPTJRC_PROD_TOKEN
from tenacity import Retrying, stop_after_attempt


def fetch_pdf_content(path: Path, limit_length: Optional[int] = None):
    title, full_text = "", ""
    with pymupdf.open(path) as pdf:
        title = pdf.metadata.get("title", "No title").strip()  # type: ignore

        for page in pdf:
            full_text += page.get_text()  # type: ignore

        if limit_length is not None and limit_length < len(full_text):
            full_text = full_text[:limit_length] + "..."

    return title, full_text


def generate_common_topics(
    model: OpenAICompatibleModel, system_prompt: str, files: list[Path]
):
    common_topics = model.generate(
        [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": "\n\n----------\n\n".join(
                    f"ATTACHMENT {i + 1} ({path.name}):\n\n{fetch_pdf_content(path)[1]}"
                    for i, path in enumerate(files)
                ),
            },
        ]
    )

    topics = re.findall(r"```point_\d+\n(.*?)\n```", common_topics, flags=re.S)
    explanations = re.findall(
        r"```explanation_\d+\n(.*?)\n```", common_topics, flags=re.S
    )

    if len(topics) == 0:
        raise ValueError("No common topic found")
    if len(topics) != len(explanations):
        raise ValueError("Mismatched number of topics and explanations")
    return topics, explanations


def improve_question(question: str, model: OpenAICompatibleModel) -> str:
    system_prompt = open(
        Path(__file__).parent / "system_prompts" / "improve_question.txt"
    ).read()
    improved_question = model.generate(
        [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": question,
            },
        ]
    )
    return improved_question


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "fileset",
        type=str,
        choices=[f.name for f in (Path(__file__).parent / "files").iterdir()],
        help="The name of the folder containing the set of files to use to build the dataset.",
    )
    argparser.add_argument(
        "--max-topics",
        type=int,
        default=5,
        help="The maximum number of common topics to find for each file combination.",
    )
    argparser.add_argument(
        "-n",
        "--tasks-per-topic",
        type=int,
        default=3,
        help="The number of tasks to create for each topic. Multiples of 6 are preferred for an even difficulty distribution.",
    )
    argparser.add_argument(
        "--confidence",
        type=int,
        default=5,
        help="The number of attempts for an LLM to solve each task before it is considered 'unsolvable' without access to the file content. A task is added only if the LLM fails for this many attempts.",
    )
    args = argparser.parse_args()

    TASKLIST_NAME = f"DocRetrieval-{args.fileset}"

    # set paths
    documents_path = Path(__file__).parent / "files" / args.fileset
    system_prompts_path = Path(__file__).parent / "system_prompts"
    tasklist_path = PROJECT_ROOT / "tasklists" / "custom" / TASKLIST_NAME
    tasks_path = tasklist_path / "tasks.json"
    task_files_path = tasklist_path / "task_files"
    metadata_path = tasklist_path / "info.json"

    log_path = Path(__file__).parent / "___log.txt"
    log_path.unlink(missing_ok=True)

    # load system prompts
    system_prompts: dict[str, str] = {}
    for path in system_prompts_path.glob("**/*.txt"):
        if path.suffix == ".txt":
            with open(path) as f:
                system_prompts[
                    str(path.relative_to(system_prompts_path).parent / path.stem)
                ] = f.read()
    print(list(system_prompts.keys()), box=True, box_title="Loaded system prompts")

    # initialize model
    assert GPTJRC_PROD_API_URL is not None, (
        "GPTJRC_PROD_API_URL is not set in the environment variables."
    )
    model = OpenAICompatibleModel(
        "openai/gpt-oss-120b", GPTJRC_PROD_API_URL, GPTJRC_PROD_TOKEN
    )

    tasks = []

    documents = [path for path in documents_path.iterdir() if path.suffix == ".pdf"]

    # create all combinations of files
    combinations = []
    for r in range(1, len(documents)):  # sets of 1, 2, and 3 files
        combinations.extend(itertools.combinations(documents, r))
    combinations.reverse()  # start with larger combinations

    for files in combinations:
        # find common topic
        try:
            print(f"Generating common topics for {[f.name for f in files]}...", end="")
            topics, explanations = Retrying(stop=stop_after_attempt(5))(
                generate_common_topics,
                model,
                system_prompts["find_common_topics"].replace(
                    "<<<n_files>>>", str(len(files))
                ),
                files,
            )
            print(":check_mark:")
        except Exception:
            print(
                f"[red]Failed to find common topics, skipping file combination {[f.name for f in files]}.[/]"
            )
            continue

        # limit number of topics
        topics = topics[: args.max_topics]
        explanations = explanations[: args.max_topics]

        for i, topic in enumerate(topics):
            print(
                f"[bold]{topic}[/]\n\n{explanations[i]}",
                box=True,
                box_title=f"Topic {i + 1}",
            )

            # generate tasks
            task_count = 0
            while task_count < args.tasks_per_topic:
                task_count += 1

                # create task id
                task_id = f"{TASKLIST_NAME}_{'_'.join(f.stem.replace(' ', '_') for f in files)}_{i}_{task_count}"

                # set difficulty modifiers
                difficulty_modifiers = {
                    "easy": "low difficulty",
                    "medium": "moderate difficulty",
                    "hard": "very high difficulty, even",
                }
                difficulty_key = {1: "easy", 2: "medium", 0: "hard"}[task_count % 3]

                # generate question, complete with answer, references, and difficulty score
                complete_question = model.generate(
                    [
                        {
                            "role": "system",
                            "content": system_prompts["generate_question"].replace(
                                "<<<difficulty_modifier>>>",
                                difficulty_modifiers[difficulty_key],
                            ),
                        },
                        {
                            "role": "user",
                            "content": "\n\n----------\n\n".join(
                                f"ATTACHMENT {i + 1} ({path.name}):\n\n{fetch_pdf_content(path)[1]}"
                                for i, path in enumerate(files)
                            )
                            + f"\n\nCOMMON TOPIC:\n{topic}"
                            + f"\n\nEXPLANATION:\n{explanations[i]}",
                        },
                    ]
                )

                # use regex to extract question, answer, references, and difficulty score
                try:
                    pattern = r"```.*?\n(.*?)\n```"
                    task = re.findall(pattern, complete_question, re.DOTALL)
                    task = {
                        "id": task_id,
                        "objective": task[0],
                        "expected": task[1],
                        "references": task[2],
                        "difficulty": task[3],
                        "documents": [path.name for path in files],
                        "topic": topic,
                        "attachment": "",
                        "custom_verificator": "",
                    }
                    print(
                        f"[bold]Task {task_count}[/]  ({difficulty_key} - {task['difficulty']})[/]\n[dim]{task['objective']}[/]"
                    )
                except Exception:
                    print("[red]Failed to parse generated question, retrying.[/]")
                    task_count -= 1
                    continue

                task["objective"] = improve_question(task["objective"], model)
                print(f"[green]{task['objective']}[/]")

                count = 0
                correct = False

                while not correct and count < args.confidence:
                    count += 1

                    # generate answer to the question without access to the file
                    system_prompt = system_prompts["tester"]
                    available_files = random.sample(
                        files, k=len(files) - 1
                    )  # simulate missing access to one file
                    if len(available_files) > 0:
                        system_prompt += (
                            "You also have access to the following attachments:"
                            + "\n\n----------\n\n".join(
                                f"ATTACHMENT {i + 1} ({path.name}):\n\n{fetch_pdf_content(path)[1]}"
                                for i, path in enumerate(available_files)
                            )
                        )
                    answer = model.generate(
                        [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": task["objective"]},
                        ]
                    )

                    # if judge says it's incorrect (needs access to files in order to be answered), add it to the dataset
                    judgement = model.generate(
                        [
                            {"role": "system", "content": system_prompts["judge"]},
                            {
                                "role": "user",
                                "content": f"QUESTION\n{task['objective']}\n\nCORRECT ANSWER\n{task['expected']}\n\nPROVIDED ANSWER\n{answer}",
                            },
                        ]
                    )

                    try:
                        reasoning = re.findall(
                            r"```reasoning\n(.*?)\n```", judgement, flags=re.S
                        )[0]
                        verdict = re.findall(
                            r"```verdict\n(.*?)\n```", judgement, flags=re.S
                        )[0]
                        assert verdict in ["Correct", "Incorrect"]
                    except (
                        IndexError,
                        AssertionError,
                    ):  # no verdict or incorrect syntax, just redo it
                        count -= 1
                        continue

                    correct |= verdict == "Correct"
                    print("[green].[/]" if not correct else "[red]F[/]", end="")

                    print(
                        f"Task {task_count} ({difficulty_key} - {task['difficulty']}) -- Check #{count}:\n{task['objective']}\n\nExpected:\n{task['expected']}\n\nProvided:\n{answer}\n\nJudge reasoning:\n{reasoning}\n\nVerdict:\n{verdict}\n",
                        file_path=log_path,
                        file_only=True,
                    )

                    if correct:  # task is not good, try with a new one
                        task_count -= 1
                        break

                print()
                if not correct:
                    tasks.append(task)

    # save task and task files (pdf)
    Path(tasks_path.parent).mkdir(parents=True, exist_ok=True)
    with open(tasks_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

    Path(task_files_path).mkdir(parents=True, exist_ok=True)
    for path in (Path(__file__).parent / "files" / args.fileset).iterdir():
        shutil.copy2(path, task_files_path / path.name)

    Path(metadata_path.parent).mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "name": TASKLIST_NAME,
                "id": f"PALACE/DocRetrieval-{args.fileset}",
                "[deprecating in favor of 'original'] type": "[deprecating in favor of 'original'] custom",
                "original": True,
                "config": args.fileset,
                "split": None,
                "category": "QA",
            },
            f,
            ensure_ascii=False,
            indent=4,
        )


if __name__ == "__main__":
    main()
