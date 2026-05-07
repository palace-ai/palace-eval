import argparse
import base64
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import filetype
from datasets import load_dataset
from huggingface_hub import dataset_info as hf_dataset_info, get_collection, hf_hub_download, login
from huggingface_hub.utils.tqdm import disable_progress_bars
from palace.utils.paths import TASKLISTS_PATH
from palace.utils.printing import loading, print
from palace.utils.secrets import HUGGINGFACE_TOKEN

PALACE_HF_COLLECTION = "jrc-ai/palace"

_logged_in = False
disable_progress_bars()


@dataclass
class DownloadEvent:
    """Progress event emitted during download_all()."""
    status: str  # "downloading" | "done" | "skipped" | "error"
    name: str
    current: int  # dataset index (1-based)
    total: int  # total datasets
    rows_done: int = 0
    total_rows: int = 0
    total_bytes: int = 0


def _ensure_login():
    global _logged_in
    if _logged_in:
        return
    if not HUGGINGFACE_TOKEN:
        raise EnvironmentError(
            "A HuggingFace token is required for this dataset. "
            "Please set the HUGGINGFACE_TOKEN environment variable in your .env file."
        )
    login(token=HUGGINGFACE_TOKEN)
    _logged_in = True


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
    on_progress: Callable[[DownloadEvent], None] | None = None,
    _progress_ctx: tuple[int, int] | None = None,
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
                on_progress=on_progress,
                _progress_ctx=_progress_ctx,
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

    # Use streaming to get row-level progress
    dataset = load_dataset(path=id, name=config, split=split, streaming=True)
    split_info = dataset.info.splits.get(split) if dataset.info.splits else None
    total_rows = split_info.num_examples if split_info else 0
    total_bytes = split_info.num_bytes if split_info else 0

    ctx_current, ctx_total = _progress_ctx or (0, 0)
    if on_progress:
        on_progress(DownloadEvent(status="downloading", name=name, current=ctx_current, total=ctx_total, total_rows=total_rows, total_bytes=total_bytes))

    # Iterate and collect rows
    dataset_rows = []
    for i, row in enumerate(dataset):
        dataset_rows.append(row)
        if on_progress and i % 100 == 0:
            on_progress(DownloadEvent(status="downloading", name=name, current=ctx_current, total=ctx_total, rows_done=i + 1, total_rows=total_rows, total_bytes=total_bytes))

    if on_progress:
        on_progress(DownloadEvent(status="downloading", name=name, current=ctx_current, total=ctx_total, rows_done=len(dataset_rows), total_rows=total_rows, total_bytes=total_bytes))

    tasks = []
    for i, row in enumerate(dataset_rows):
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
        and dataset_rows
        and column_names["attachment"] in dataset_rows[0]
    ):
        attachments_dir = Path(tasklist_path / "task_files")
        attachments_dir.mkdir(parents=True, exist_ok=True)

        for attachment in [
            row[column_names["attachment"]]
            for row in dataset_rows
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


def download_all(
    on_progress: Callable[[DownloadEvent], None] | None = None,
    skip_existing: bool = False,
    tasklists: list[str] | None = None,
) -> None:
    """Download all PALACE datasets (private collection + public).

    Args:
        on_progress: Optional callback invoked with DownloadEvent for real-time progress.
        skip_existing: Skip datasets that already exist locally.
        tasklists: If provided, only download these tasklist names.
    """
    # Build full list of datasets to download
    all_items: list[dict] = []

    # Private collection
    try:
        _ensure_login()
        collection = get_collection(PALACE_HF_COLLECTION)
        for item in collection.items:
            if item.item_type == "dataset":
                name = item.item_id.replace("jrc-ai/", "")
                if tasklists and name not in tasklists:
                    continue
                if skip_existing and (TASKLISTS_PATH / name).exists():
                    continue
                all_items.append({"name": name, "id": item.item_id, "_private": True})
    except EnvironmentError:
        print("[yellow]Skipping private PALACE collection (no HUGGINGFACE_TOKEN set).")

    # Public datasets
    with open(Path(__file__).parent / "public_datasets_info.json") as f:
        public_info = json.load(f)

    if HUGGINGFACE_TOKEN:
        try:
            _ensure_login()
        except Exception:
            pass

    # Expand list splits
    expanded = []
    for item in public_info:
        if isinstance(item["split"], list):
            for s in item["split"]:
                expanded.append({**item, "split": s, "name": f"{item['name']}-{s}"})
        else:
            expanded.append(item)

    for item in expanded:
        if tasklists and item["name"] not in tasklists:
            continue
        if skip_existing and (TASKLISTS_PATH / item["name"]).exists():
            continue
        all_items.append({**item, "_private": False})

    total = len(all_items)
    for idx, item in enumerate(all_items, 1):
        name = item["name"]

        # Check gated
        if not item.get("_private") and not HUGGINGFACE_TOKEN:
            try:
                info = hf_dataset_info(item["id"])
                if info.gated:
                    if on_progress:
                        on_progress(DownloadEvent(status="skipped", name=name, current=idx, total=total))
                    print(f"   [yellow]:cross_mark: {name} is gated. Skipping.")
                    continue
            except Exception:
                pass

        # Download
        with loading() as ld:
            ld.description = f"[cyan]Downloading [bold]{name}[/bold]..."

            if item.get("_private"):
                metadata = hf_hub_download(repo_id=item["id"], filename="info.json", repo_type="dataset")
                with open(metadata) as f:
                    metadata = json.load(f)
                download_tasklist(
                    name=name, id=item["id"], split="test",
                    keep_custom_columns=True, task_type=metadata.get("task_type", ""),
                    on_progress=on_progress, _progress_ctx=(idx, total),
                )
            else:
                dl_args = {k: v for k, v in item.items() if k != "_private"}
                download_tasklist(**dl_args, on_progress=on_progress, _progress_ctx=(idx, total))

        if on_progress:
            on_progress(DownloadEvent(status="done", name=name, current=idx, total=total))
        print(f"   :check_box_with_check:[cyan] {name}")


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

    download_all(
        skip_existing=args.skip_existing,
        tasklists=args.tasklists,
    )
