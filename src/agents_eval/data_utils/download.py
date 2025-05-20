import base64
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Dict, Optional

import filetype
from datasets import load_dataset
from huggingface_hub import hf_hub_download, login

from agents_eval.utils.paths import PROJECT_ROOT
from agents_eval.utils.secrets import HUGGINGFACE_TOKEN

login(token=HUGGINGFACE_TOKEN)


def download_tasklist(
    name: str,
    id: str,
    split: str,
    column_names: Dict[str, str],
    config: Optional[str] = None,
    attachment_path: Optional[str] = None,
    raw_bytes_attachment: Optional[bool] = False,
    category: Optional[str] = None,
    label_mapping: Optional[Dict[str, str]] = None,
) -> None:
    dataset = load_dataset(id, config, split=split, download_mode="force_redownload")
    df_dataset = dataset.to_pandas()

    tasks = []
    for i, row in df_dataset.iterrows():
        # Get attachment name
        attachment = (
            row[column_names["attachment"]] if "attachment" in column_names else ""
        )
        if raw_bytes_attachment and attachment != "":
            attachment = _get_filename_for_base64(attachment)

        # Convert dataset-specific task format to my own task format
        task = {
            "id": f"{name}_{row[column_names['id']] if 'id' in column_names else i}",
            "objective": row[column_names["objective"]],
            "expected": row[column_names["expected"]],
            "difficulty": f"{name}_{row[column_names['difficulty']]}"
            if "difficulty" in column_names
            else "",
            "attachment": attachment,
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
    if column_names.get("attachment") is not None:
        attachments_dir = Path(output_path / "task_files")
        attachments_dir.mkdir(parents=True, exist_ok=True)

        for filename in df_dataset[df_dataset[column_names["attachment"]] != ""][
            column_names["attachment"]
        ]:
            # attachment is present as a file name to download
            if not raw_bytes_attachment:
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
                    shutil.move(temp_path, attachments_dir / filename)

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

            # attachment is present as a raw byte string to decode
            else:
                base64_payload = _extract_base64_payload(filename)
                binary_data = base64.b64decode(base64_payload)

                output_file = _get_filename_for_base64(filename)
                with open(attachments_dir / output_file, "wb") as f:
                    f.write(binary_data)

    print(f"Tasklist successfully saved to {output_path}.")


def _extract_base64_payload(base64_string: str) -> str:
    # Regex to match Data URI and capture the Base64 payload
    pattern = r"^data:[a-z]+/[a-z]+;base64,(.+)$"
    match = re.match(pattern, base64_string.strip())
    return (
        match.group(1) if match else base64_string
    )  # Return payload or full string if there is no prefix


def _get_filename_for_base64(base64_str: str) -> str:
    # Strip Data URI prefix if present
    if base64_str.startswith("data:"):
        base64_str = base64_str.split(",")[1]

    # Decode and hash
    binary_data = base64.b64decode(base64_str)

    full_hash = hashlib.sha256(binary_data).hexdigest()
    filename = full_hash[:24]  # Use the first 24 characters of the hash as the filename

    guess = filetype.guess(binary_data)
    extension = guess.extension if guess else "bin"

    return f"{filename}.{extension}"


if __name__ == "__main__":
    with open(
        PROJECT_ROOT / "src" / "agents_eval" / "data_utils" / "tasklists_info.json"
    ) as f:
        tasklists_info = json.load(f)

    for tasklist_info in tasklists_info:
        download_tasklist(**tasklist_info)
