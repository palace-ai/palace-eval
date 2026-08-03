# Copyright (C) 2025 European Union
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the European Union Public Licence (EUPL) v. 1.2
# as published by the European Union.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# European Union Public Licence for more details.
#
# You should have received a copy of the European Union Public Licence
# along with this program. If not, see <https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12>.

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import filetype
from datasets import load_dataset
from huggingface_hub import dataset_info as hf_dataset_info
from huggingface_hub import get_collection, hf_hub_download, list_repo_tree, login
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

    status: str  # "downloading" | "processing" | "files" | "done" | "skipped" | "error"
    name: str
    current: int  # dataset index (1-based)
    total: int  # total datasets
    rows_done: int = 0
    total_rows: int = 0
    total_bytes: int = 0
    files_done: int = 0
    total_files: int = 0


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


def _glob_has_wildcards(pattern: str) -> bool:
    return any(c in pattern for c in "*?[")


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
    group_from: str | None = None,
    interleave_groups: bool = False,
    penalize_unsupported: bool = False,
    on_progress: Callable[[DownloadEvent], None] | None = None,
    _progress_ctx: tuple[int, int] | None = None,
) -> None:
    if custom_verificator is not None and not bool(
        re.match(
            r"^\s*def\s+verify\s*\(\s*pred\s*,\s*truth\s*\)\s*:\s*",
            custom_verificator,
        )
    ):
        raise ValueError(
            f"If custom_verificator is specified, it must follow the signature 'def verify(pred, truth) -> bool', found {custom_verificator}."
        )

    # Multi-config: iterate configs and combine into single dataset stream
    if isinstance(config, list) and isinstance(split, list):
        # Both config and split are lists: iterate all combinations
        def _multi_config_split_stream():
            for cfg in config:
                for s in split:
                    ds = load_dataset(
                        path=id, name=cfg, split=s, streaming=True, storage_options={"client_kwargs": {"timeout": 120}}
                    )
                    for row in ds:
                        row = dict(row)
                        if group_from == "config":
                            row["_group"] = cfg
                        elif group_from == "split":
                            row["_group"] = s
                        yield row

        dataset = _multi_config_split_stream()
        split_info = None
    elif isinstance(split, list):

        def _multi_split_stream():
            for s in split:
                ds = load_dataset(
                    path=id, name=config, split=s, streaming=True, storage_options={"client_kwargs": {"timeout": 120}}
                )
                for row in ds:
                    if group_from == "split":
                        row = dict(row)
                        row["_group"] = s
                    yield row

        dataset = _multi_split_stream()
        split_info = None
    elif isinstance(config, list):

        def _multi_config_stream():
            for cfg in config:
                ds = load_dataset(
                    path=id, name=cfg, split=split, streaming=True, storage_options={"client_kwargs": {"timeout": 120}}
                )
                for row in ds:
                    if group_from == "config":
                        row = dict(row)
                        row["_group"] = cfg
                    yield row

        dataset = _multi_config_stream()
        split_info = None
    else:
        # Use streaming to get row-level progress (timeout detects stalled connections)
        dataset = load_dataset(
            path=id, name=config, split=split, streaming=True, storage_options={"client_kwargs": {"timeout": 120}}
        )
        split_info = dataset.info.splits.get(split) if dataset.info.splits else None

    total_rows = split_info.num_examples if split_info else 0
    total_bytes = split_info.num_bytes if split_info else 0

    ctx_current, ctx_total = _progress_ctx or (0, 0)
    if on_progress:
        on_progress(
            DownloadEvent(
                status="downloading",
                name=name,
                current=ctx_current,
                total=ctx_total,
                total_rows=total_rows,
                total_bytes=total_bytes,
            )
        )

    # Prepare attachments dir early for inline writes during streaming
    tasklist_path = TASKLISTS_PATH / name
    os.makedirs(tasklist_path, exist_ok=True)
    _att_cols_raw = column_names.get("attachments") or column_names.get("attachment")
    _attachment_cols: list[str] | None = [_att_cols_raw] if isinstance(_att_cols_raw, str) else _att_cols_raw
    if inline_attachment and _attachment_cols:
        (tasklist_path / "task_files").mkdir(parents=True, exist_ok=True)

    # Detect dynamic classes (classes_from references in task_type_fields)
    _dynamic_labels = []  # list of (label_index, from_column, class_naming)
    if task_type_fields:
        for i, label in enumerate(task_type_fields.get("labels", [])):
            classes_from = label.get("classes_from")
            if classes_from:
                _dynamic_labels.append((i, classes_from["from_column"], classes_from.get("class_naming", "letters")))

    # Columns we need to keep in memory
    _needed_cols = set()
    for v in column_names.values():
        if isinstance(v, list):
            _needed_cols.update(v)
        else:
            _needed_cols.add(v)
    for _, col, _ in _dynamic_labels:
        if isinstance(col, list):
            _needed_cols.update(col)
        else:
            _needed_cols.add(col)
    if group_from:
        _needed_cols.add("_group")
    if keep_custom_columns:
        _needed_cols = None  # keep all

    # Iterate and collect rows (inline attachments written immediately to avoid memory accumulation)
    dataset_rows = []
    for i, row in enumerate(dataset):
        # Write inline attachments immediately and replace blobs with filenames
        if inline_attachment and _attachment_cols:
            for att_col in _attachment_cols:
                raw = row.get(att_col)
                if raw:
                    # Handle PIL Image objects (HuggingFace Image feature)
                    from PIL import Image as PILImage

                    if isinstance(raw, PILImage.Image):
                        import io

                        buf = io.BytesIO()
                        fmt = raw.format or "PNG"
                        raw.save(buf, format=fmt)
                        img_bytes = buf.getvalue()
                        ext = fmt.lower()
                        filename = hashlib.sha256(img_bytes).hexdigest()[:24] + f".{ext}"
                        with open(tasklist_path / "task_files" / filename, "wb") as f:
                            f.write(img_bytes)
                    elif isinstance(raw, dict) and "array" in raw and "sampling_rate" in raw:
                        # HuggingFace Audio feature: {"path": ..., "array": ndarray, "sampling_rate": int}
                        import io as _io
                        import wave as _wave

                        import numpy as np

                        arr = np.asarray(raw["array"])
                        # Normalize float to int16
                        if arr.dtype.kind == "f":
                            arr = (arr * 32767).clip(-32768, 32767).astype(np.int16)
                        buf = _io.BytesIO()
                        with _wave.open(buf, "wb") as wf:
                            wf.setnchannels(1 if arr.ndim == 1 else arr.shape[1])
                            wf.setsampwidth(2)
                            wf.setframerate(raw["sampling_rate"])
                            wf.writeframes(arr.tobytes())
                        audio_bytes = buf.getvalue()
                        filename = hashlib.sha256(audio_bytes).hexdigest()[:24] + ".wav"
                        with open(tasklist_path / "task_files" / filename, "wb") as f:
                            f.write(audio_bytes)
                    elif isinstance(raw, dict) and "path" in raw and "bytes" in raw and raw["bytes"]:
                        # HuggingFace Audio/Image with bytes: {"path": "file.wav", "bytes": b"..."}
                        audio_bytes = raw["bytes"]
                        ext = Path(raw["path"]).suffix.lower() if raw.get("path") else ".bin"
                        filename = hashlib.sha256(audio_bytes).hexdigest()[:24] + ext
                        with open(tasklist_path / "task_files" / filename, "wb") as f:
                            f.write(audio_bytes)
                    elif isinstance(raw, (bytes, bytearray)):
                        filename = _get_filename(raw)
                        if filename:
                            with open(tasklist_path / "task_files" / filename, "wb") as f:
                                f.write(raw)
                    elif isinstance(raw, str) and raw.strip():
                        filename = _get_filename(raw)
                        if filename:
                            attachment_type = _string_type(raw)
                            if attachment_type == "base64":
                                data = base64.b64decode(_extract_base64_payload(raw))
                            else:
                                data = raw
                            with open(
                                tasklist_path / "task_files" / filename,
                                "w" if attachment_type == "text" else "wb",
                                encoding="utf-8" if attachment_type == "text" else None,
                            ) as f:
                                f.write(data)
                    else:
                        filename = ""
                    row = {**row, att_col: filename}

        # Strip large unused columns to save memory
        if _needed_cols is not None:
            row = {k: v for k, v in row.items() if k in _needed_cols}
        dataset_rows.append(row)
        if on_progress and i % 100 == 0:
            on_progress(
                DownloadEvent(
                    status="downloading",
                    name=name,
                    current=ctx_current,
                    total=ctx_total,
                    rows_done=i + 1,
                    total_rows=total_rows,
                    total_bytes=total_bytes,
                )
            )

    if on_progress:
        on_progress(
            DownloadEvent(
                status="processing",
                name=name,
                current=ctx_current,
                total=ctx_total,
                rows_done=len(dataset_rows),
                total_rows=total_rows,
                total_bytes=total_bytes,
            )
        )

    tasks = []
    seen_ids = set()
    for i, row in enumerate(dataset_rows):
        # Get attachment(s) — already filenames for inline_attachment (processed during streaming)
        if _attachment_cols:
            attachments = [row.get(col, "") for col in _attachment_cols if row.get(col)]
        else:
            attachments = []

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
            "custom_verificator": custom_verificator
            if custom_verificator is not None and custom_verificator != ""
            else row[column_names["custom_verificator"]]
            if "custom_verificator" in column_names and column_names["custom_verificator"] in row
            else "",
        }

        # Set group field if group_from is configured
        if group_from and "_group" in row:
            task["group"] = row["_group"]
        elif "group" in column_names and column_names["group"] in row:
            task["group"] = row[column_names["group"]]

        # Store attachments
        if attachments:
            task["attachments"] = attachments

        # Add any additional columns from the original dataset if keep_custom_columns is True
        if keep_custom_columns:
            for k, v in row.items():
                if k not in column_names.values():
                    task[k] = v  # type: ignore

        # Add default labels for Classification tasks
        if default_labels is not None:
            task["labels"] = default_labels

        # Resolve dynamic classes per-task
        if _dynamic_labels:
            resolved_labels = []
            for label_idx, col, naming in _dynamic_labels:
                if isinstance(col, list):
                    options = [row.get(c, "") for c in col]
                else:
                    options = row.get(col, [])
                # Shuffle if correct_index is specified (e.g., GPQA where correct is always first)
                correct_idx = task_type_fields["labels"][label_idx].get("classes_from", {}).get("correct_index")
                if correct_idx is not None:
                    import random

                    rng = random.Random(task["id"])  # deterministic per task
                    indices = list(range(len(options)))
                    rng.shuffle(indices)
                    options = [options[j] for j in indices]
                    correct_letter_idx = indices.index(correct_idx)
                else:
                    correct_letter_idx = None
                if naming == "letters":
                    names = [chr(ord("A") + j) for j in range(len(options))]
                elif naming == "numbers":
                    names = [str(j + 1) for j in range(len(options))]
                else:
                    names = [chr(ord("A") + j) for j in range(len(options))]
                classes = [{"name": n, "condition": str(o)} for n, o in zip(names, options)]
                label_def = {**task_type_fields["labels"][label_idx], "classes": classes}
                resolved_labels.append(label_def)
                # Set expected to the shuffled correct letter
                if correct_letter_idx is not None:
                    label_name = label_def["name"]
                    task["labels"] = {label_name: names[correct_letter_idx]}
                    task["expected"] = ""
            task["task_type_fields"] = {"labels": resolved_labels}

            # Set per-task expected label from the expected column (non-shuffled case)
            if task.get("expected") and resolved_labels and "labels" not in task:
                label_name = resolved_labels[0]["name"]
                task["labels"] = {label_name: task["expected"]}
                task["expected"] = ""

        # Add task to list if it doesn't already exist
        if task["id"] not in seen_ids:
            seen_ids.add(task["id"])
            # Build per-task constraints from columns (for InstructionFollowing)
            if task_type_fields and "constraints_from_columns" in task_type_fields:
                cfc = task_type_fields["constraints_from_columns"]
                types_col = cfc["types_column"]
                params_col = cfc["params_column"]
                types_list = row.get(types_col, [])
                params_list = row.get(params_col, [])
                constraints = []
                for ctype, kwargs in zip(types_list, params_list):
                    active_params = {k: v for k, v in kwargs.items() if v is not None} if kwargs else {}
                    constraints.append({"type": ctype, "params": active_params})
                task["task_type_fields"] = {"constraints": constraints}
            tasks.append(task)

    # Map labels if label_mapping is provided
    if label_mapping is not None:
        for task in tasks:
            if task.get("expected"):
                task["expected"] = label_mapping.get(str(task["expected"]), task["expected"])
            if task.get("labels"):
                task["labels"] = {k: label_mapping.get(str(v), v) for k, v in task["labels"].items()}

    # Write metadata (info.json) — tasklist_path already created above
    # Download tasklist metadata if available, otherwise create it
    try:
        metadata = hf_hub_download(repo_id=id, filename="info.json", repo_type="dataset")
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
            # Strip dynamic classes references (resolved per-task, not per-tasklist)
            if _dynamic_labels:
                clean_labels = []
                for label in task_type_fields.get("labels", []):
                    clean = {k: v for k, v in label.items() if k != "classes"}
                    clean_labels.append(clean)
                info["task_type_fields"] = {"labels": clean_labels}
            else:
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

    # Download and save task files (attachments) — skip inline (already written during streaming)
    _att_col = column_names.get("attachments") or column_names.get("attachment")
    if not inline_attachment and _att_col is not None and dataset_rows and _att_col in dataset_rows[0]:
        attachments_dir = Path(tasklist_path / "task_files")
        attachments_dir.mkdir(parents=True, exist_ok=True)

        attachments_to_download = []
        for row in dataset_rows:
            val = row.get(_att_col, "")
            if isinstance(val, list):
                attachments_to_download.extend(v for v in val if v)
            elif val:
                attachments_to_download.append(val)
        total_files = len(attachments_to_download)

        if on_progress and total_files:
            on_progress(
                DownloadEvent(
                    status="files",
                    name=name,
                    current=ctx_current,
                    total=ctx_total,
                    files_done=0,
                    total_files=total_files,
                )
            )

        temp_dir = tasklist_path / ".dl_tmp"
        for file_idx, attachment in enumerate(attachments_to_download):
            dest = attachments_dir / attachment
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Skip files already downloaded (e.g., from interrupted previous run)
            if dest.exists():
                if on_progress:
                    on_progress(
                        DownloadEvent(
                            status="files",
                            name=name,
                            current=ctx_current,
                            total=ctx_total,
                            files_done=file_idx + 1,
                            total_files=total_files,
                        )
                    )
                continue

            try:
                temp_path = hf_hub_download(
                    repo_id=id,
                    filename=os.path.join(attachment_path, attachment),  # type: ignore
                    repo_type="dataset",
                    local_dir=temp_dir,
                )
                shutil.move(temp_path, dest)
            except Exception as e:
                print(f"Error downloading {attachment}: {e}")

            if on_progress:
                on_progress(
                    DownloadEvent(
                        status="files",
                        name=name,
                        current=ctx_current,
                        total=ctx_total,
                        files_done=file_idx + 1,
                        total_files=total_files,
                    )
                )

        # Clean up temp directory once after all files
        try:
            shutil.rmtree(temp_dir)
        except OSError:
            pass

    # Read info.json to determine paths for environment and task_files
    with open(tasklist_path / "info.json") as f:
        _info = json.load(f)

    # Helper: download files from repo to local tasklist directory
    def _download_repo_files(filenames: list[str]):
        for filename in filenames:
            dest = tasklist_path / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                continue
            try:
                temp = hf_hub_download(repo_id=id, filename=filename, repo_type="dataset")
                shutil.copy2(temp, dest)
            except Exception as e:
                print(f"  Warning: failed to download {filename}: {e}")

    def _list_repo_path(path: str) -> list[str]:
        try:
            return [
                f.rfilename
                for f in list_repo_tree(id, path_in_repo=path, repo_type="dataset", recursive=True)
                if hasattr(f, "rfilename")
            ]
        except Exception:
            return []

    # List full repo tree once (for glob matching)
    from fnmatch import fnmatch

    try:
        _all_repo_files = [
            f.rfilename for f in list_repo_tree(id, repo_type="dataset", recursive=True) if hasattr(f, "rfilename")
        ]
    except Exception:
        _all_repo_files = []

    def _match_glob(pattern: str) -> list[str]:
        return [f for f in _all_repo_files if fnmatch(f, pattern)]

    # Download environment + companions directories
    env_dirs = set()
    if "env" in _info:
        for cfg in _info["env"].values():
            env_dirs.add(cfg.get("path", "environment"))
    else:
        env_dirs.add("environment")
    for env_path in env_dirs:
        _download_repo_files(_list_repo_path(env_path))
        companions_path = str(Path(env_path).parent / "companions")
        _download_repo_files(_list_repo_path(companions_path))

    # Download task_files
    task_files_path = _info.get("task_files_path", "task_files")
    if _glob_has_wildcards(task_files_path):
        tf_files = [
            f
            for f in _all_repo_files
            if any(fnmatch("/".join(f.split("/")[:i]), task_files_path) for i in range(1, len(f.split("/"))))
        ]
    else:
        tf_files = _list_repo_path(task_files_path)
    if tf_files:
        if on_progress:
            on_progress(
                DownloadEvent(
                    status="files",
                    name=name,
                    current=ctx_current,
                    total=ctx_total,
                    files_done=0,
                    total_files=len(tf_files),
                )
            )
        for file_idx, filename in enumerate(tf_files):
            dest = tasklist_path / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                try:
                    temp = hf_hub_download(repo_id=id, filename=filename, repo_type="dataset")
                    shutil.copy2(temp, dest)
                except Exception as e:
                    print(f"  Warning: failed to download {filename}: {e}")
            if on_progress:
                on_progress(
                    DownloadEvent(
                        status="files",
                        name=name,
                        current=ctx_current,
                        total=ctx_total,
                        files_done=file_idx + 1,
                        total_files=len(tf_files),
                    )
                )

    # Download task files matching tasks_path; write compiled fallback if none found in repo
    _tasks_path_pattern = _info.get("tasks_path", "tasks.json")
    task_json_files = _match_glob(_tasks_path_pattern)
    if task_json_files:
        _download_repo_files(task_json_files)
    else:
        # Interleave tasks by group (round-robin) if requested
        if interleave_groups and tasks and tasks[0].get("group"):
            from itertools import zip_longest

            group_buckets: dict[str, list] = {}
            for t in tasks:
                group_buckets.setdefault(t.get("group", ""), []).append(t)
            interleaved = []
            for batch in zip_longest(*group_buckets.values()):
                for t in batch:
                    if t is not None:
                        interleaved.append(t)
            tasks = interleaved

        out_path = _tasks_path_pattern if not _glob_has_wildcards(_tasks_path_pattern) else "tasks.json"
        with open(tasklist_path / out_path, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=4)

    # Add penalize_unsupported to info.json if requested
    if penalize_unsupported:
        info_path = tasklist_path / "info.json"
        with open(info_path) as f:
            info_data = json.load(f)
        info_data["penalize_unsupported"] = True
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info_data, f, ensure_ascii=False, indent=4)

    # Write .palace-complete marker (authoritative completion signal)
    (tasklist_path / ".palace-complete").touch()


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
        if re.fullmatch(r"^data:[a-z]+/[a-z]+;base64,[A-Za-z0-9+/=]+$", s):  # Looks like Base64
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


def _build_download_list(skip_existing: bool = False, tasklists: list[str] | None = None) -> list[dict]:
    """Build the list of datasets to download (private + public)."""
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
                if skip_existing and (TASKLISTS_PATH / name / ".palace-complete").exists():
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

    for item in public_info:
        if tasklists and item["name"] not in tasklists:
            continue
        if skip_existing and (TASKLISTS_PATH / item["name"] / ".palace-complete").exists():
            continue
        all_items.append({**item, "_private": False})

    return all_items


def list_downloads(skip_existing: bool = False, tasklists: list[str] | None = None) -> list[dict]:
    """Return info about datasets that would be downloaded.

    Args:
        skip_existing: Exclude datasets that already exist locally.
        tasklists: If provided, only include these tasklist names.

    Returns:
        List of dicts with 'name' and 'category' keys.
    """
    return [
        {"name": item["name"], "category": item.get("category")}
        for item in _build_download_list(skip_existing, tasklists)
    ]


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
    all_items = _build_download_list(skip_existing, tasklists)

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

            try:
                if item.get("_private"):
                    metadata = hf_hub_download(repo_id=item["id"], filename="info.json", repo_type="dataset")
                    with open(metadata) as f:
                        metadata = json.load(f)
                    download_tasklist(
                        name=name,
                        id=item["id"],
                        split="test",
                        keep_custom_columns=True,
                        task_type=metadata.get("task_type", ""),
                        on_progress=on_progress,
                        _progress_ctx=(idx, total),
                    )
                else:
                    dl_args = {k: v for k, v in item.items() if k != "_private"}
                    download_tasklist(**dl_args, on_progress=on_progress, _progress_ctx=(idx, total))
            except Exception as e:
                print(f"   [red]:cross_mark: {name} failed: {e}. Skipping.[/red]")
                if on_progress:
                    on_progress(DownloadEvent(status="error", name=name, current=idx, total=total))
                continue

        if on_progress:
            on_progress(DownloadEvent(status="done", name=name, current=idx, total=total))
        print(f"   :check_box_with_check:[cyan] {name}")


def main():
    argparser = argparse.ArgumentParser(description="Download PALACE datasets from Hugging Face.")
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
