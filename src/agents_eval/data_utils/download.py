import json
import os
import shutil
from typing import Dict, Optional

from datasets import load_dataset
from huggingface_hub import hf_hub_download, login

from agents_eval.utils.paths import PROJECT_ROOT
from agents_eval.utils.secrets import HUGGINGFACE_TOKEN

login(token=HUGGINGFACE_TOKEN)


def download_tasklist(
    name: str,
    id: str,
    config: str,
    split: str,
    column_names: Dict[str, str],
    attachment_path: Optional[str] = None,
    category: Optional[str] = None,
    label_mapping: Optional[Dict[str, str]] = None,
) -> None:
    dataset = load_dataset(id, config, split=split, download_mode="force_redownload")
    df_dataset = dataset.to_pandas()

    tasks = []
    for i, row in df_dataset.iterrows():
        # Convert dataset-specific task format to my own task format
        task = {
            "id": f"{name}_{row[column_names['id']] if column_names['id'] is not None else i}",
            "objective": row[column_names["objective"]],
            "expected": row[column_names["expected"]],
            "difficulty": f"{name}_{row[column_names['difficulty']]}"
            if column_names["difficulty"] is not None
            else "",
            "attachment": row[column_names["attachment"]]
            if column_names["attachment"] is not None
            else "",
        }
        # Add task to list if it doesn't already exist
        if task["id"] not in [t["id"] for t in tasks]:
            tasks.append(task)

    # Map labels if label_mapping is provided
    if label_mapping is not None:
        for task in tasks:
            task["expected"] = label_mapping[task["expected"]]

    # Save tasklist tasks and tasklist metadata to file
    output_path = PROJECT_ROOT / "tasklists" / name
    os.makedirs(output_path, exist_ok=True)
    with open(output_path / "tasks.json", "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)
    with open(output_path / "info.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "name": name,
                "id": id,
                "config": config,
                "split": split,
                "category": category,
            },
            f,
            ensure_ascii=False,
            indent=4,
        )

    # Download and save task files (attachments)
    if column_names["attachment"] is not None:
        os.makedirs(os.path.join(output_path, "task_files"), exist_ok=True)
        for filename in df_dataset[df_dataset[column_names["attachment"]] != ""][
            column_names["attachment"]
        ]:
            try:
                temp_path = hf_hub_download(
                    repo_id=id,
                    filename=os.path.join(attachment_path, filename),
                    repo_type="dataset",
                    local_dir=os.path.join(output_path, "task_files"),
                    local_dir_use_symlinks=False,
                    force_download=True,
                )

                # Move to final location
                final_path = os.path.join(
                    os.path.join(output_path, "task_files"), filename
                )
                shutil.move(temp_path, final_path)

            except Exception as e:
                print(f"Error downloading {filename}: {e}")

            try:
                shutil.rmtree(
                    os.path.join(output_path, "task_files/2023")
                )  # this needs to be generalized
                shutil.rmtree(os.path.join(output_path, "task_files/.cache"))
                print(f"Removed empty subdirectories under {output_path}")
            except OSError as e:
                print(f"Error removing subdirectories: {e}")

    print(f"Tasklist successfully saved to {output_path}.")


if __name__ == "__main__":
    TASKLISTS_INFO = [
        {
            "name": "GAIA",
            "id": "gaia-benchmark/GAIA",
            "config": "2023_all",
            "split": "validation",
            "column_names": {
                "id": "task_id",
                "objective": "Question",
                "expected": "Final answer",
                "difficulty": "Level",
                "attachment": "file_name",
            },
            "attachment_path": "2023/validation",
            "category": "QA",
        },
        {
            "name": "SimpleQA",
            "id": "basicv8vc/SimpleQA",
            "config": None,
            "split": "test",
            "column_names": {
                "id": None,
                "objective": "problem",
                "expected": "answer",
                "difficulty": None,
                "attachment": None,
            },
            "attachment_path": None,
            "category": "QA",
        },
        {
            "name": "AssistantBench",
            "id": "AssistantBench/AssistantBench",
            "config": None,
            "split": "validation",
            "column_names": {
                "id": "id",
                "objective": "task",
                "expected": "answer",
                "difficulty": "difficulty",
                "attachment": None,
            },
            "attachment_path": None,
            "category": "QA",
        },
        {
            "name": "Fever",
            "id": "fever/fever",
            "config": "v1.0",
            "split": "labelled_dev",
            "column_names": {  # maps what i want -> what is in the dataset
                "id": "id",
                "objective": "claim",
                "expected": "label",
                "difficulty": None,
                "attachment": None,
            },
            "attachment_path": None,
            "category": "Claim Verification",
            "label_mapping": {  # maps what is in the dataset -> what i want
                "SUPPORTS": "True",
                "REFUTES": "False",
                "NOT ENOUGH INFO": "Not Enough Info",
            },
        },
    ]

    for tasklist_info in TASKLISTS_INFO:
        download_tasklist(**tasklist_info)
