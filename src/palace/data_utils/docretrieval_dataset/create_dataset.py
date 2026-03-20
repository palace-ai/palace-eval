import argparse
import itertools
import json
import re
import shutil
from pathlib import Path
from typing import Optional

import pymupdf
from palace.models.api_model import APIModel
from palace.utils.constants import OPENAI_LIKE_API_BASE_URL
from palace.utils.paths import TASKLISTS_PATH
from palace.utils.printing import print
from palace.utils.secrets import OPENAI_LIKE_API_KEY
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


def format_attachments(files: list[Path]) -> str:
    """Format files as attachments using filename as identifier."""
    return "\n\n----------\n\n".join(
        f"ATTACHMENT ({path.name}):\n\n{fetch_pdf_content(path)[1]}" for path in files
    )


def generate_common_topics(model: APIModel, system_prompt: str, files: list[Path]):
    common_topics = model.generate(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": format_attachments(files)},
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


def generate_tasks(
    model: APIModel,
    system_prompt: str,
    files: list[Path],
    topic: str,
    explanation: str,
    n_tasks: int,
):
    """Generate multiple tasks in a single pass, returns list of parsed task dicts."""
    prompt = system_prompt.replace("<<<n_questions>>>", str(n_tasks))
    response = model.generate(
        [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": format_attachments(files)
                + f"\n\nCOMMON TOPIC:\n{topic}"
                + f"\n\nEXPLANATION:\n{explanation}",
            },
        ]
    )

    tasks = []
    for i in range(1, n_tasks + 1):
        question = re.search(rf"<question_{i}>(.*?)</question_{i}>", response, re.S)
        answer = re.search(rf"<answer_{i}>(.*?)</answer_{i}>", response, re.S)
        contribution = re.search(
            rf"<contribution_{i}>(.*?)</contribution_{i}>", response, re.S
        )
        references = re.search(
            rf"<references_{i}>(.*?)</references_{i}>", response, re.S
        )
        if question and answer:
            tasks.append(
                {
                    "text": question.group(1).strip(),
                    "answer": answer.group(1).strip(),
                    "contribution": contribution.group(1).strip()
                    if contribution
                    else "",
                    "references": references.group(1).strip() if references else "",
                }
            )
    if not tasks:
        raise ValueError("No tasks parsed from response")
    return tasks


def improve_task(objective: str, model: APIModel) -> str:
    system_prompt = open(
        Path(__file__).parent / "system_prompts" / "improve_question.txt"
    ).read()
    return model.generate(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": objective},
        ]
    )


def validate_task(
    task: dict,
    files: list[Path],
    model: APIModel,
    system_prompts: dict,
    confidence: int,
    log_path: Path,
) -> bool:
    """
    Validate that task requires ALL files.
    Returns True if task is valid (tester fails with any single file removed).
    """
    for excluded_idx in range(len(files)):
        available_files = [f for i, f in enumerate(files) if i != excluded_idx]
        excluded_file = files[excluded_idx].name

        for attempt in range(confidence):
            system_prompt = system_prompts["tester"]
            if available_files:
                system_prompt += (
                    "\n\nYou have access to the following attachments:\n\n"
                    + format_attachments(available_files)
                )

            answer = model.generate(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": task["objective"]},
                ]
            )
            if not answer:
                continue

            judgement = model.generate(
                [
                    {"role": "system", "content": system_prompts["judge"]},
                    {
                        "role": "user",
                        "content": f"QUESTION\n{task['objective']}\n\nCORRECT ANSWER\n{task['expected']}\n\nPROVIDED ANSWER\n{answer}",
                    },
                ]
            )
            if not judgement:
                continue

            try:
                reasoning = re.findall(
                    r"```reasoning\n(.*?)\n```", judgement, flags=re.S
                )[0]
                verdict = re.findall(r"```verdict\n(.*?)\n```", judgement, flags=re.S)[
                    0
                ]
                assert verdict in ["Correct", "Incorrect"]
            except (IndexError, AssertionError):
                continue

            # Log validation attempt
            print(
                f"\n{'=' * 80}\n"
                f"VALIDATION: {task['id']}\n"
                f"EXCLUDED FILE: {excluded_file}\n"
                f"AVAILABLE FILES: {[f.name for f in available_files]}\n"
                f"ATTEMPT: {attempt + 1}/{confidence}\n"
                f"{'=' * 80}\n"
                f"QUESTION:\n{task['objective']}\n\n"
                f"EXPECTED ANSWER:\n{task['expected']}\n\n"
                f"TESTER ANSWER:\n{answer}\n\n"
                f"JUDGE REASONING:\n{reasoning}\n\n"
                f"VERDICT: {verdict}\n"
                f"{'=' * 80}\n",
                file_path=log_path,
                file_only=True,
            )

            if verdict == "Correct":
                print(f"[red]F({excluded_file})[/]", end="")
                return False

            print("[green].[/]", end="")

    return True


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "fileset",
        type=str,
        choices=[
            f.name for f in (Path(__file__).parent / "filesets").iterdir() if f.is_dir()
        ],
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
        default=6,
        help="The number of tasks to generate for each topic (generated in single batch for diversity).",
    )
    argparser.add_argument(
        "--confidence",
        type=int,
        default=3,
        help="Number of attempts per file removal to validate task difficulty.",
    )
    args = argparser.parse_args()

    TASKLIST_NAME = f"DocRetrieval-{args.fileset}"

    documents_path = Path(__file__).parent / "filesets" / args.fileset
    system_prompts_path = Path(__file__).parent / "system_prompts"
    tasklist_path = TASKLISTS_PATH / TASKLIST_NAME
    tasks_path = tasklist_path / "tasks.json"
    task_files_path = tasklist_path / "task_files"
    metadata_path = tasklist_path / "info.json"

    log_path = Path(__file__).parent / "___log.txt"
    log_path.unlink(missing_ok=True)

    system_prompts: dict[str, str] = {}
    for path in system_prompts_path.glob("**/*.txt"):
        with open(path) as f:
            system_prompts[
                str(path.relative_to(system_prompts_path).parent / path.stem)
            ] = f.read()
    print(list(system_prompts.keys()), box=True, box_title="Loaded system prompts")

    assert OPENAI_LIKE_API_BASE_URL is not None, "OPENAI_LIKE_API_BASE_URL is not set"
    model = APIModel("minimax-m2", OPENAI_LIKE_API_BASE_URL, OPENAI_LIKE_API_KEY)

    tasks = []
    documents = [path for path in documents_path.iterdir() if path.suffix == ".pdf"]

    combinations = []
    for r in range(1, 1 + min(3, len(documents))):
        combinations.extend(itertools.combinations(documents, r))
    combinations.reverse()

    for files in combinations:
        files = list(files)

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
                f"[red]Failed to find common topics, skipping {[f.name for f in files]}.[/]"
            )
            continue

        topics = topics[: args.max_topics]
        explanations = explanations[: args.max_topics]

        for topic_idx, topic in enumerate(topics):
            print(
                f"[bold]{topic}[/]\n\n{explanations[topic_idx]}",
                box=True,
                box_title=f"Topic {topic_idx + 1}",
            )

            try:
                raw_tasks = Retrying(stop=stop_after_attempt(3))(
                    generate_tasks,
                    model,
                    system_prompts["generate_questions"],
                    files,
                    topic,
                    explanations[topic_idx],
                    args.tasks_per_topic,
                )
            except Exception as e:
                print(f"[red]Failed to generate tasks: {e}[/]")
                continue

            for t_idx, raw_task in enumerate(raw_tasks):
                task_id = f"{TASKLIST_NAME}_{'_'.join(f.stem.replace(' ', '_') for f in files)}_{topic_idx}_{t_idx}"

                task = {
                    "id": task_id,
                    "objective": raw_task["text"],
                    "expected": raw_task["answer"],
                    "contribution": raw_task["contribution"],
                    "references": raw_task["references"],
                    "difficulty": len(files),  # difficulty = number of files required
                    "documents": [path.name for path in files],
                    "topic": topic,
                    "attachment": "",
                    "custom_verificator": "",
                }

                print(
                    f"[bold]Task {t_idx + 1}[/] (difficulty {task['difficulty']})\n[dim]{task['objective']}[/]"
                )

                task["objective"] = improve_task(task["objective"], model)
                print(f"[green]{task['objective']}[/]")

                print("Validating: ", end="")
                if validate_task(
                    task, files, model, system_prompts, args.confidence, log_path
                ):
                    print(" [green]✓ Valid[/]")
                    tasks.append(task)
                else:
                    print(" [red]✗ Invalid (answerable without all files)[/]")

        #         break  # DEBUG: stop after first task
        #     break  # DEBUG: stop after first topic
        # break  # DEBUG: stop after first file combination

    Path(tasks_path.parent).mkdir(parents=True, exist_ok=True)
    with open(tasks_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

    Path(task_files_path).mkdir(parents=True, exist_ok=True)
    for path in documents_path.iterdir():
        shutil.copy2(path, task_files_path / path.name)

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "name": TASKLIST_NAME,
                "id": f"jrc-ai/DocRetrieval-{args.fileset}",
                "original": True,
                "config": "default",
                "split": "test",
                "category": "Agentic",
                "task_type": "QA",
            },
            f,
            ensure_ascii=False,
            indent=4,
        )

    print(f"\n[bold green]Done! Generated {len(tasks)} tasks.[/]")


if __name__ == "__main__":
    main()
