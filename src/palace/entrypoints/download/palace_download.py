import argparse
import base64
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import filetype
from datasets import load_dataset
from huggingface_hub import get_collection, hf_hub_download, login
from huggingface_hub.utils.tqdm import disable_progress_bars
from palace.utils.paths import TASKLISTS_PATH
from palace.utils.printing import loading, print
from palace.utils.secrets import HUGGINGFACE_TOKEN

PALACE_HF_COLLECTION = "jrc-ai/palace"

login(token=HUGGINGFACE_TOKEN)
disable_progress_bars()


def download_tasklist(
    name: str,
    id: str,
    split: list[str] | str,
    config: str = "default",
    column_names: dict[str, str] = {
        "id": "id",
        "objective": "objective",
        "expected": "expected",
        "difficulty": "difficulty",
        "attachment": "attachment",
        "custom_verificator": "custom_verificator",
    },
    keep_custom_columns: bool = False,
    attachment_path: str | None = "task_files",
    inline_attachment: bool | None = None,
    category: str | None = None,
    task_type: str | None = None,
    task_type_fields: dict | None = None,
    default_labels: dict[str, str] | None = None,
    label_mapping: dict[str, str] | None = None,
    custom_verificator: str | None = None,
) -> None:
    if isinstance(split, list):
        for s in split:
            download_tasklist(
                name=f"{name}-{s}",
                id=id,
                split=s,
                config=config,
                column_names=column_names,
                attachment_path=attachment_path,
                inline_attachment=inline_attachment,
                category=category,
                task_type=task_type,
                task_type_fields=task_type_fields,
                default_labels=default_labels,
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
    dataset = dataset.to_list()  # type: ignore
    tasks = []
    for i, row in enumerate(dataset):
        # Get attachment name
        attachment = (
            row[column_names["attachment"]]
            if "attachment" in column_names and column_names["attachment"] in row
            else ""
        )
        if inline_attachment:
            attachment = _get_filename(attachment)

        # Convert dataset-specific task format to my own task format
        task = {
            "id": f"{name}_{row[column_names['id']] if 'id' in column_names else i}",
            "objective": row[column_names["objective"]],
            "expected": row[column_names["expected"]]
            if "expected" in column_names and column_names["expected"] in row
            else "",
            "difficulty": f"{name}_{row[column_names['difficulty']]}"
            if "difficulty" in column_names and column_names["difficulty"] in row
            else "",
            "attachment": attachment,
            "custom_verificator": custom_verificator
            if custom_verificator is not None and custom_verificator != ""
            else row[column_names["custom_verificator"]]
            if "custom_verificator" in column_names
            and column_names["custom_verificator"] in row
            else "",
        }

        # Add any additional columns from the original dataset if keep_custom_columns is True
        if keep_custom_columns:
            for k, v in row.items():
                if k not in column_names.values():
                    task[k] = v  # type: ignore

        # Add default labels for Classification tasks
        if default_labels is not None:
            task["labels"] = default_labels

        # Add task to list if it doesn't already exist
        if task["id"] not in [t["id"] for t in tasks]:
            tasks.append(task)

    # Map labels if label_mapping is provided
    if label_mapping is not None:
        for task in tasks:
            task["expected"] = label_mapping[task["expected"]]

    # Save tasklist tasks and metadata
    tasklist_path = TASKLISTS_PATH / name
    os.makedirs(tasklist_path, exist_ok=True)
    with open(tasklist_path / "tasks.json", "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

    # Download tasklist metadata if available, otherwise create it
    try:
        metadata = hf_hub_download(
            repo_id=id, filename="info.json", repo_type="dataset"
        )
        with open(metadata) as f:
            metadata = json.load(f)
        with open(tasklist_path / "info.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)
    except Exception:
        info = {
            "name": name,
            "id": id,
            "original": False,
            "config": config,
            "split": split,
            "category": category,
            "task_type": task_type,
        }
        if task_type_fields is not None:
            info["task_type_fields"] = task_type_fields
        with open(tasklist_path / "info.json", "w", encoding="utf-8") as f:
            json.dump(
                info,
                f,
                ensure_ascii=False,
                indent=4,
            )

    # Auto-detect modalities if not already declared in info.json
    info_path = tasklist_path / "info.json"
    with open(info_path) as f:
        info_data = json.load(f)
    if "input_modalities" not in info_data:
        from palace.utils.multimodal import detect_modalities

        info_data["input_modalities"] = detect_modalities(tasks)
        info_data.setdefault("output_modalities", ["text"])
        # Remove legacy key if present
        info_data.pop("modalities", None)
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info_data, f, ensure_ascii=False, indent=4)

    # Download and save task files (attachments)
    if (
        column_names.get("attachment") is not None
        and column_names["attachment"] in dataset[0]
    ):
        attachments_dir = Path(tasklist_path / "task_files")
        attachments_dir.mkdir(parents=True, exist_ok=True)

        for attachment in [
            row[column_names["attachment"]]
            for row in dataset
            if row.get(column_names["attachment"], "") != ""
        ]:
            # attachment is present as a file name to download
            if not inline_attachment:
                temp_dir = tasklist_path / ".dl_tmp"
                try:
                    temp_path = hf_hub_download(
                        repo_id=id,
                        filename=os.path.join(attachment_path, attachment),  # type: ignore
                        repo_type="dataset",
                        local_dir=temp_dir,
                        force_download=True,
                    )

                    # Move to final location
                    dest = attachments_dir / attachment
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(temp_path, dest)

                except Exception as e:
                    print(f"Error downloading {attachment}: {e}")

                try:
                    shutil.rmtree(temp_dir)
                except OSError as e:
                    print(f"Error removing subdirectories: {e}")

            # attachment is present within the dataframe, either as plain text or as a raw byte string to decode
            else:
                attachment_type = _string_type(attachment)
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
            reencoded = base64.b64encode(decoded).decode("utf-8")
            if reencoded == s:
                return "base64"  # Valid Base64
    except Exception as e:
        print(e)

    return "text"  # Not Base64, valid UTF-8 → plain text


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
    # Check s is not empty
    if not s or (isinstance(s, str) and s.strip() == ""):
        return ""

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


def main():
    argparser = argparse.ArgumentParser(
        description="Download PALACE datasets from Hugging Face."
    )
    argparser.add_argument(
        "-t",
        "--tasklists",
        nargs="+",
        help="Names of the tasklists to download. If not specified, all tasklists are downloaded.",
    )
    argparser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip downloading datasets that already exist locally.",
    )
    args = argparser.parse_args()

    # Download private (from palace hf)
    collection = get_collection(PALACE_HF_COLLECTION)
    collection = [
        {"id": item.item_id, "name": item.item_id.replace("jrc-ai/", "")}
        for item in collection.items
        if item.item_type == "dataset"
    ]
    print(
        f":small_blue_diamond: [blue]Starting to download [bold]{len(collection)}[/bold] items from the PALACE Hugging Face collection"
    )

    # filter by --tasklists argument if provided
    if args.tasklists:
        collection = [item for item in collection if item["name"] in args.tasklists]
        print(
            f"   [cyan]Filtered to [bold]{len(collection)}[/bold] items based on --tasklists argument."
        )

    # If --skip-existing is set, filter out items that already exist locally
    if args.skip_existing:
        exists = [
            item for item in collection if (TASKLISTS_PATH / item["name"]).exists()
        ]
        collection = [item for item in collection if item not in exists]
        print(
            f"   [cyan]Skipping [bold]{len(exists)}[/bold] items that already exist locally."
        )

    print(f"   [cyan]Downloading [bold]{len(collection)}[/bold] items...")
    for item in collection:
        with loading() as ld:
            ld.description = (
                f"[cyan]Downloading [bold]{item['name']} (from {item['id']})[/bold]..."
            )

            # Get dataset metadata
            metadata = hf_hub_download(
                repo_id=item["id"], filename="info.json", repo_type="dataset"
            )
            with open(metadata) as f:
                metadata = json.load(f)

            download_tasklist(
                name=item["name"],
                id=item["id"],
                split="test",
                keep_custom_columns=True,
                task_type=metadata.get("task_type", ""),
            )
        print(f"   :check_box_with_check:[cyan] {item['name']}")

    # Download public
    with open(Path(__file__).parent / "public_datasets_info.json") as f:
        tasklists_info = json.load(f)
    print(
        f":small_blue_diamond: [blue]Starting to download [bold]{len(tasklists_info)}[/bold] items from public Hugging Face datasets"
    )

    # convert items with list splits into multiple items with single splits
    tasklists_info = [
        item
        if isinstance(item["split"], str)
        else {**item, "split": s, "name": f"{item['name']}-{s}"}
        for item in tasklists_info
        for s in (item["split"] if isinstance(item["split"], list) else [item["split"]])
    ]

    # filter by --tasklists argument if provided
    if args.tasklists:
        tasklists_info = [
            info for info in tasklists_info if info["name"] in args.tasklists
        ]
        print(
            f"   [cyan]Filtered to [bold]{len(tasklists_info)}[/bold] items based on --tasklists argument."
        )

    # If --skip-existing is set, filter out items that already exist locally
    if args.skip_existing:
        exists = [
            info for info in tasklists_info if (TASKLISTS_PATH / info["name"]).exists()
        ]
        tasklists_info = [info for info in tasklists_info if info not in exists]
        print(
            f"   [cyan]Skipping [bold]{len(exists)}[/bold] items that already exist locally."
        )

    print(f"   [cyan]Downloading [bold]{len(tasklists_info)}[/bold] items...")
    for tasklist_info in tasklists_info:
        with loading() as ld:
            ld.description = f"[cyan]Downloading [bold]{tasklist_info['name']} (from {tasklist_info['id']})[/bold]..."
            download_tasklist(**tasklist_info)
        print(f"   :check_box_with_check:[cyan]  {tasklist_info['name']}")
