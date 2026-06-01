"""Convert HealthBench (openai/healthbench) into 3 palace tasklists.

Subsets:
- HealthBench Hard: hard_*.jsonl (1000 tasks)
- HealthBench Realistic: consensus_*.jsonl (3671 tasks)
- HealthBench Hard Hallucinations: filtered from main eval by hallucination theme

Each task has rubric criteria mapped to CriteriaEvaluation absolute mode.
"""

import json
from pathlib import Path

from huggingface_hub import hf_hub_download

from palace.utils.paths import TASKLISTS_PATH

REPO_ID = "openai/healthbench"

# Map HealthBench axis tags to dimension names
AXIS_MAP = {
    "axis:accuracy": "accuracy",
    "axis:completeness": "completeness",
    "axis:context_awareness": "context_awareness",
    "axis:communication_quality": "communication_quality",
    "axis:instruction_following": "instruction_following",
}


def _convert_row(row: dict, idx: int, prefix: str) -> dict:
    """Convert a HealthBench row to a palace task."""
    # Build objective from prompt messages
    messages = row["prompt"]
    if len(messages) == 1:
        objective = messages[0]["content"]
    else:
        parts = []
        for msg in messages:
            role = msg["role"].capitalize()
            parts.append(f"{role}: {msg['content']}")
        objective = "\n\n".join(parts)

    # Convert rubrics to criteria
    criteria = []
    for i, rubric in enumerate(row["rubrics"]):
        # Determine dimension from tags
        dimension = None
        for tag in rubric.get("tags", []):
            if tag in AXIS_MAP:
                dimension = AXIS_MAP[tag]
                break

        criterion = {
            "name": f"criterion_{i}",
            "description": rubric["criterion"][:500],  # truncate very long cluster rubrics
            "points": rubric["points"],
        }
        if dimension:
            criterion["dimension"] = dimension
        criteria.append(criterion)

    task = {
        "id": f"{prefix}_{row.get('prompt_id', idx)}",
        "objective": objective,
        "expected": "",
        "task_type_fields": {"mode": "absolute", "criteria": criteria},
    }

    # Add ideal completion as reference if available
    ideal = row.get("ideal_completions_data")
    if isinstance(ideal, dict) and ideal.get("ideal_completion"):
        task["expected"] = ideal["ideal_completion"]

    return task


def _save_tasklist(name: str, tasks: list[dict], category: str = "Domain Knowledge"):
    """Save a tasklist to disk."""
    tasklist_path = TASKLISTS_PATH / name
    tasklist_path.mkdir(parents=True, exist_ok=True)

    # Clean task_type_fields
    for t in tasks:
        pass  # no cleanup needed

    json.dump(tasks, open(tasklist_path / "tasks.json", "w"), indent=2, ensure_ascii=False)
    json.dump(
        {
            "name": name,
            "id": "openai/healthbench",
            "original": False,
            "task_type": "Criteria Evaluation",
            "category": category,
            "task_type_fields": {
                "mode": "absolute",
            },
        },
        open(tasklist_path / "info.json", "w"),
        indent=2,
    )
    print(f"Saved {len(tasks)} tasks to {tasklist_path}")


def main():
    # Download JSONL files
    print("Downloading HealthBench files...")
    hard_path = hf_hub_download(REPO_ID, "hard_2025-05-08-21-00-10.jsonl", repo_type="dataset")
    consensus_path = hf_hub_download(REPO_ID, "consensus_2025-05-09-20-00-46.jsonl", repo_type="dataset")

    # Load
    with open(hard_path) as f:
        hard_rows = [json.loads(line) for line in f]
    with open(consensus_path) as f:
        consensus_rows = [json.loads(line) for line in f]

    print(f"Loaded: hard={len(hard_rows)}, consensus={len(consensus_rows)}")

    # HealthBench Hard
    hard_tasks = [_convert_row(row, i, "HealthBench-Hard") for i, row in enumerate(hard_rows)]
    _save_tasklist("HealthBench Hard", hard_tasks)

    # HealthBench Realistic (consensus)
    consensus_tasks = [_convert_row(row, i, "HealthBench-Realistic") for i, row in enumerate(consensus_rows)]
    _save_tasklist("HealthBench Realistic", consensus_tasks)

    print(f"\nDone! Created 2 tasklists:")
    print(f"  HealthBench Hard: {len(hard_tasks)} tasks")
    print(f"  HealthBench Realistic: {len(consensus_tasks)} tasks")


if __name__ == "__main__":
    main()
