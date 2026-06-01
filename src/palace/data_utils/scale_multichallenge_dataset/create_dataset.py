"""Convert Scale MultiChallenge into a palace tasklist.

Format: Multi-turn conversation + target question → YES/NO answer.
The conversation is formatted into a single objective string.
"""

import json
from pathlib import Path

from datasets import load_dataset

from palace.utils.paths import TASKLISTS_PATH


def _format_conversation(conv: dict) -> str:
    """Format conversation dict {'role': [...], 'content': [...]} into readable transcript."""
    parts = []
    for role, content in zip(conv["role"], conv["content"]):
        parts.append(f"{role.capitalize()}: {content}")
    return "\n\n".join(parts)


def main():
    print("Downloading Scale MultiChallenge...")
    ds = load_dataset("ScaleAI/MultiChallenge", split="test", streaming=True)

    tasks = []
    for i, row in enumerate(ds):
        conversation = _format_conversation(row["conversation"])
        target_question = row["target_question"]

        objective = (
            f"Here is a conversation between a user and an assistant:\n\n"
            f"{conversation}\n\n"
            f"---\n\n"
            f"Based on the conversation above, answer the following question with YES or NO:\n"
            f"{target_question}"
        )

        tasks.append({
            "id": f"MultiChallenge_{row['question_id']}",
            "objective": objective,
            "expected": "",
            "labels": {"Answer": row["pass_criteria"]},  # YES or NO
            "difficulty": row.get("axis", ""),
        })

    # Save
    tasklist_path = TASKLISTS_PATH / "Scale MultiChallenge"
    tasklist_path.mkdir(parents=True, exist_ok=True)

    json.dump(tasks, open(tasklist_path / "tasks.json", "w"), indent=2, ensure_ascii=False)
    json.dump(
        {
            "name": "Scale MultiChallenge",
            "id": "ScaleAI/MultiChallenge",
            "original": False,
            "task_type": "Classification",
            "category": "General Reasoning",
            "task_type_fields": {
                "labels": [{
                    "name": "Answer",
                    "description": "Whether the assistant's behavior in the conversation meets the specified criterion.",
                    "classes": [
                        {"name": "YES", "condition": "if the criterion is satisfied"},
                        {"name": "NO", "condition": "if the criterion is not satisfied"},
                    ]
                }]
            },
        },
        open(tasklist_path / "info.json", "w"),
        indent=2,
    )

    print(f"Saved {len(tasks)} tasks to {tasklist_path}")
    print(f"First task objective ({len(tasks[0]['objective'])} chars):")
    print(tasks[0]["objective"][:200] + "...")


if __name__ == "__main__":
    main()
