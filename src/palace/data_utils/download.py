import base64
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Optional

import filetype
from datasets import load_dataset
from huggingface_hub import hf_hub_download, login

from palace.utils.paths import PROJECT_ROOT
from palace.utils.printing import print
from palace.utils.secrets import HUGGINGFACE_TOKEN

login(token=HUGGINGFACE_TOKEN)


def download_tasklist(
    name: str,
    id: str,
    split: list[str] | str,
    column_names: dict[str, str],
    config: Optional[str] = None,
    attachment_path: Optional[str] = None,
    inline_attachment: Optional[bool] = None,
    category: Optional[str] = None,
    label_mapping: Optional[dict[str, str]] = None,
    custom_verificator: Optional[str] = None,
) -> None:
    if isinstance(split, list):
        for s in split:
            download_tasklist(
                name=f"{name}-{s}",
                id=id,
                split=s,
                column_names=column_names,
                config=config,
                attachment_path=attachment_path,
                inline_attachment=inline_attachment,
                category=category,
                label_mapping=label_mapping,
                custom_verificator=custom_verificator,
            )
        return

    if custom_verificator is not None and not bool(
        re.match(
            r"^\s*def\s+verify\s*\(\s*pred\s*,\s*truth\s*\)\s*:\s*",
            custom_verificator,
        )
    ):
        raise ValueError(
            f"If custom_verificator is specified, it must follow the signature 'def verify(pred, truth) -> bool', found {custom_verificator}."
        )

    dataset = load_dataset(path=id, name=config, split=split)
    df_dataset = dataset.to_pandas()  # type: ignore
    tasks = []
    for i, row in df_dataset.iterrows():  # type: ignore
        # Get attachment name
        attachment = (
            row[column_names["attachment"]] if "attachment" in column_names else ""
        )
        if inline_attachment:
            attachment = _get_filename(attachment)

        # Convert dataset-specific task format to my own task format
        task = {
            "id": f"{name}_{row[column_names['id']] if 'id' in column_names else i}",
            "objective": row[column_names["objective"]],
            "expected": row[column_names["expected"]],
            "difficulty": f"{name}_{row[column_names['difficulty']]}"
            if "difficulty" in column_names
            else "",
            "attachment": attachment,
            "custom_verificator": custom_verificator
            if custom_verificator is not None and custom_verificator != ""
            else "",
        }
        # Add task to list if it doesn't already exist
        if task["id"] not in [t["id"] for t in tasks]:
            tasks.append(task)

    # Map labels if label_mapping is provided
    if label_mapping is not None:
        for task in tasks:
            task["expected"] = label_mapping[task["expected"]]

    # Save tasklist tasks
    tasks_path = PROJECT_ROOT / "tasklists" / "automated" / name
    os.makedirs(tasks_path, exist_ok=True)
    with open(tasks_path / "tasks.json", "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

    # Save tasklist metadata
    metadata_path = PROJECT_ROOT / "tasklists" / "metadata" / name
    os.makedirs(metadata_path, exist_ok=True)
    with open(metadata_path / "info.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "name": name,
                "id": id,
                "type": "automated",
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
        attachments_dir = Path(tasks_path / "task_files")
        attachments_dir.mkdir(parents=True, exist_ok=True)

        for attachment in df_dataset[df_dataset[column_names["attachment"]] != ""][  # type: ignore
            column_names["attachment"]
        ]:
            # attachment is present as a file name to download
            if not inline_attachment:
                try:
                    temp_path = hf_hub_download(
                        repo_id=id,
                        filename=os.path.join(attachment_path, attachment),  # type: ignore
                        repo_type="dataset",
                        local_dir=os.path.join(tasks_path, "task_files"),
                        local_dir_use_symlinks=False,
                        force_download=True,
                    )

                    # Move to final location
                    shutil.move(temp_path, attachments_dir / attachment)

                except Exception as e:
                    print(f"Error downloading {attachment}: {e}")

                try:
                    shutil.rmtree(
                        os.path.join(tasks_path, "task_files/2023")
                    )  # this needs to be generalized
                    shutil.rmtree(os.path.join(tasks_path, "task_files/.cache"))
                    print(f"Removed empty subdirectories under {tasks_path}")
                except OSError as e:
                    print(f"Error removing subdirectories: {e}")

            # attachment is present within the dataframe, either as plain text or as a raw byte string to decode
            else:
                attachment_type = _string_type(attachment)
                # print(f"\nAttachment ({attachment_type}):\n{attachment[:100]}")
                if attachment_type == "base64":
                    attachment = _extract_base64_payload(attachment)
                    attachment = base64.b64decode(attachment)

                output_file = _get_filename(attachment)  # type: ignore
                with open(
                    attachments_dir / output_file,
                    "w" if attachment_type == "text" else "wb",
                    encoding="utf-8" if attachment_type == "text" else None,
                ) as f:
                    f.write(attachment)

    print(f"Tasklist successfully saved to {tasks_path}.")


def _string_type(s):
    """Returns:
    - "text" if plain UTF-8 text
    - "base64" if valid Base64 (likely encoded binary)
    - "binary" if invalid UTF-8 (likely raw binary)
    """
    try:
        assert s == s.encode("utf-8").decode("utf-8")
    except UnicodeError:
        return "binary"  # Invalid UTF-8 → raw binary

    try:
        if re.fullmatch(
            r"^data:[a-z]+/[a-z]+;base64,[A-Za-z0-9+/=]+$", s
        ):  # Looks like Base64
            s = _extract_base64_payload(s)
            decoded = base64.b64decode(s + "==", validate=False)  # era validate=True
            print("Looks like base64")
            reencoded = base64.b64encode(decoded).decode("utf-8")
            print(f"{s[:50]} <---> {reencoded[:50]}")
            if reencoded == s:
                return "base64"  # Valid Base64
    except Exception as e:
        print(e)

    return "text"  # Not Base64, valid UTF-8 → plain text


def _is_base64(s):
    # Check if the string is valid base64
    try:
        if isinstance(s, str):
            # Check if the string can be decoded from base64 and re-encoded to the same string
            return base64.b64encode(base64.b64decode(s)).decode("utf-8") == s
        return False
    except Exception:
        return False


def _extract_base64_payload(base64_string: str) -> str:
    # Regex to match Data URI and capture the Base64 payload
    pattern = r"^data:[a-z]+/[a-z]+;base64,(.+)$"
    match = re.match(pattern, base64_string.strip())
    return match.group(1) if match else base64_string


def _get_filename(s: str) -> str:
    """
    Accepts either a str (plain text or base64 data URI/payload) or bytes.
    Produces a deterministic filename based on sha256 of the binary content,
    and picks an extension using filetype.guess for binary data, or 'txt' for text.
    """
    # Handle bytes input
    if isinstance(s, (bytes, bytearray)):
        data_bytes = bytes(s)
        try:
            _ = data_bytes.decode("utf-8")
            string_type = "text"
        except UnicodeDecodeError:
            string_type = "binary"
    else:
        # s is a str
        string_type = _string_type(s)
        if string_type == "base64":
            payload = _extract_base64_payload(s)
            data_bytes = base64.b64decode(payload)
            string_type = "binary"
        else:
            # treat plain str as UTF-8 text
            data_bytes = s.encode("utf-8")

    # Hash the binary content
    full_hash = hashlib.sha256(data_bytes).hexdigest()
    filename = full_hash[:24]

    # Guess file type from bytes
    guess = filetype.guess(data_bytes)
    if string_type == "text":
        extension = "txt"
    else:
        extension = guess.extension if guess else "bin"

    return f"{filename}.{extension}"


def _backup_get_filename(s: str) -> str:
    string_type = _string_type(s)
    if string_type == "base64":
        s = _extract_base64_payload(s)

    data = s.decode("utf-8")  # type: ignore
    full_hash = hashlib.sha256(data).hexdigest()
    filename = full_hash[:24]  # Use the first 24 characters of the hash as the filename

    guess = filetype.guess(data)
    if string_type == "base64":
        extension = guess.extension if guess else "bin"
    else:
        extension = "txt"

    return f"{filename}.{extension}"


if __name__ == "__main__":
    with open(
        PROJECT_ROOT / "src" / "palace" / "data_utils" / "tasklists_info.json"
    ) as f:
        tasklists_info = json.load(f)

    for tasklist_info in tasklists_info:
        print(
            f"Downloading [bold]{tasklist_info['name']}[/]\n[dim]{json.dumps(tasklist_info, indent=4)}[/]"
        )
        download_tasklist(**tasklist_info)
