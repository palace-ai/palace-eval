import argparse
import json
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


def fetch_pdf_content(path: Path, limit_length: Optional[int] = None):
    title, full_text = "", ""
    with pymupdf.open(path) as pdf:
        title = pdf.metadata.get("title", "No title").strip()  # type: ignore

        for page in pdf:
            full_text += page.get_text()  # type: ignore

        if limit_length is not None and limit_length < len(full_text):
            full_text = full_text[:limit_length] + "..."

    return title, full_text


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "fileset",
        type=str,
        choices=[f.name for f in (Path(__file__).parent / "files").iterdir()],
        help="The name of the folder containing the set of files to use to build the dataset.",
    )
    argparser.add_argument(
        "-n",
        "--tasks-per-file",
        type=int,
        default=6,
        help="The number of tasks to create for each file. Multiples of 6 are preferred for an even difficulty distribution.",
    )
    argparser.add_argument(
        "--task-confidence",
        type=int,
        default=5,
        help="The number of attempts for an LLM to solve each task before it is considered 'unsolvable' without access to the file content. A task is added only if the LLM fails for this many attempts.",
    )
    args = argparser.parse_args()

    TASKLIST_NAME = f"DocRetrieval-{args.fileset}"

    # load system prompts
    system_prompts: dict[str, str] = {}
    for path in (Path(__file__).parent / "system_prompts").iterdir():
        if path.suffix == ".txt":
            with open(path) as f:
                system_prompts[path.stem] = f.read()

    # initialize model
    model = OpenAICompatibleModel(
        "openai/gpt-oss-120b", GPTJRC_PROD_API_URL, GPTJRC_PROD_TOKEN
    )

    # set paths
    tasks_path = PROJECT_ROOT / "tasklists" / "custom" / TASKLIST_NAME / "tasks.json"
    task_files_path = (
        PROJECT_ROOT / "tasklists" / "custom" / TASKLIST_NAME / "task_files"
    )
    metadata_path = (
        PROJECT_ROOT / "tasklists" / "metadata" / TASKLIST_NAME / "info.json"
    )
    log_path = Path(__file__).parent / "___log.txt"
    log_path.unlink(missing_ok=True)

    tasks = []
    count = 0
    for path in (Path(__file__).parent / "files" / args.fileset).iterdir():
        if path.suffix != ".pdf":
            continue

        count += 1
        print(f"[bold]({count}) {path.name}")

        # extract pdf
        _, full_text = fetch_pdf_content(path)

        # generate tasks
        task_count = 0
        while task_count < args.tasks_per_file:
            task_count += 1

            # create task id
            task_id = f"{TASKLIST_NAME}_{path.stem.replace(' ', '_')}_{task_count}"

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
                        "content": system_prompts["question_generator"].replace(
                            "<<<difficulty_modifier>>>",
                            difficulty_modifiers[difficulty_key],
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"ATTACHMENT ({path.name}):\n\n{full_text}",
                    },
                ]
            )

            # use regex to extract question, answer, references, and difficulty score
            pattern = r"```.*?\n(.*?)\n```"
            task = re.findall(pattern, complete_question, re.DOTALL)
            task = {
                "id": task_id,
                "objective": task[0],
                "expected": task[1],
                "references": task[2],
                "difficulty": task[3],
                "document": path.name,
                "attachment": "",
                "custom_verificator": "",
            }
            print(
                f"[bold]Task {task_count}[/]  ({difficulty_key} - {task['difficulty']})[/]\n[dim]{task['objective']}[/]"
            )

            count = 0
            correct = False
            while not correct and count < args.task_confidence:
                count += 1

                # generate answer to the question without access to the file
                answer = model.generate(
                    [
                        {"role": "system", "content": system_prompts["tester"]},
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
                    f"Task {task_count} ({difficulty_key} - {task['difficulty']}) -- Check {count}:\n{task['objective']}\n\nExpected:\n{task['expected']}\n\nProvided:\n{answer}\n\nJudge reasoning:\n{reasoning}\n\nVerdict:\n{verdict}\n",
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
                "id": "_Custom/DocRetrieval",
                "type": "custom",
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
