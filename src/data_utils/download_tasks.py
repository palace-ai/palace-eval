import json
import os
import shutil
from typing import Dict

from datasets import load_dataset
from huggingface_hub import hf_hub_download, login
from utils.secrets import HUGGINGFACE_TOKEN

login(token=HUGGINGFACE_TOKEN)

TASKLISTS_PATH = "../../tasklists"


def download_tasklist(
    tasklist_name: str,
    dataset_id: str,
    dataset_config: str,
    split: str,
    column_names: Dict[str, str],
):
    dataset = load_dataset(
        dataset_id, dataset_config, split=split, download_mode="force_redownload"
    )
    df_dataset = dataset.to_pandas()

    # Convert dataset-specific task format to my own task format
    tasks = []
    for i, row in df_dataset.iterrows():
        tasks.append(
            {
                "id": f"{tasklist_name}_{row[column_names['id']] if column_names['id'] is not None else i}",
                "objective": row[column_names["objective"]],
                "expected": row[column_names["expected"]],
                "difficulty": f"{tasklist_name}_{row[column_names['difficulty']]}"
                if column_names["difficulty"] is not None
                else "",
                "attachment": row[column_names["attachment"]]
                if column_names["attachment"] is not None
                else "",
            }
        )

    # Save tasklist to file
    output_path = os.path.join(TASKLISTS_PATH, tasklist_name)
    os.makedirs(output_path, exist_ok=True)
    with open(f"{output_path}/tasks.json", "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

    # Download and save task files (attachments)
    if column_names["attachment"] is not None:
        os.makedirs(os.path.join(output_path, "task_files"), exist_ok=True)
        for filename in df_dataset[df_dataset[column_names["attachment"]] != ""][
            column_names["attachment"]
        ]:
            try:
                temp_path = hf_hub_download(
                    repo_id=dataset_id,
                    filename=f"2023/validation/{filename}",
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
                shutil.rmtree(os.path.join(output_path, "task_files/2023"))
                shutil.rmtree(os.path.join(output_path, "task_files/.cache"))
                print(f"Removed empty subdirectories under {output_path}")
            except OSError as e:
                print(f"Error removing subdirectories: {e}")

    print(f"GAIA tasks successfully saved to {output_path}.")


DATASETS_INFO = {
    "GAIA": {
        "dataset_id": "gaia-benchmark/GAIA",
        "dataset_config": "2023_all",
        "split": "validation",
        "column_names": {
            "id": "task_id",
            "objective": "Question",
            "expected": "Final answer",
            "difficulty": "Level",
            "attachment": "file_name",
        },
    },
    "SimpleQA": {
        "dataset_id": "basicv8vc/SimpleQA",
        "dataset_config": None,
        "split": "test",
        "column_names": {
            "id": None,
            "objective": "problem",
            "expected": "answer",
            "difficulty": None,
            "attachment": None,
        },
    },
}

for tasklist_name, dataset_info in DATASETS_INFO.items():
    download_tasklist(
        tasklist_name=tasklist_name,
        dataset_id=dataset_info["dataset_id"],
        dataset_config=dataset_info["dataset_config"],
        split=dataset_info["split"],
        column_names=dataset_info["column_names"],
    )
