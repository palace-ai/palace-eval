"""
Convert ys-zong/VLGuard test set to PALACE Classification tasklist.

Produces one tasklist: VLGuard (1,558 tasks from 1,000 images).

Source: https://huggingface.co/datasets/ys-zong/VLGuard

The raw dataset has a per-image `safe` boolean and typed instructions:
  - safe image (558): has safe_instruction + unsafe_instruction → 2 tasks each
  - unsafe image (442): has one instruction (always unsafe) → 1 task each

Label mapping:
  safe image + safe_instruction   → Unsafe=No  (558 tasks)
  safe image + unsafe_instruction → Unsafe=Yes (558 tasks)
  unsafe image + instruction      → Unsafe=Yes (442 tasks)

Total: 1,558 tasks (1,000 unsafe, 558 safe)
"""

import json
import random
import zipfile
from pathlib import Path

from huggingface_hub import hf_hub_download
from palace.utils.paths import TASKLISTS_PATH

REPO_ID = "ys-zong/VLGuard"


def build_tasks() -> list[dict]:
    local = hf_hub_download(REPO_ID, "test.json", repo_type="dataset")
    with open(local, encoding="utf-8") as f:
        data = json.load(f)

    tasks = []
    for item in data:
        image = item["image"]

        if item["safe"]:
            # Safe image: two instructions (safe + unsafe)
            for ir in item["instr-resp"]:
                if "safe_instruction" in ir:
                    tasks.append(
                        {
                            "id": f"{item['id']}_safe",
                            "objective": ir["safe_instruction"],
                            "attachment": image,
                            "labels": {"Unsafe": "No"},
                        }
                    )
                elif "unsafe_instruction" in ir:
                    tasks.append(
                        {
                            "id": f"{item['id']}_unsafe",
                            "objective": ir["unsafe_instruction"],
                            "attachment": image,
                            "labels": {"Unsafe": "Yes"},
                        }
                    )
        else:
            # Unsafe image: one instruction (always unsafe)
            ir = item["instr-resp"][0]
            tasks.append(
                {
                    "id": item["id"],
                    "objective": ir["instruction"],
                    "attachment": image,
                    "labels": {"Unsafe": "Yes"},
                }
            )

    random.Random(42).shuffle(tasks)
    return tasks


def extract_images(out_dir: Path, needed: set[str]) -> None:
    local_zip = hf_hub_download(REPO_ID, "test.zip", repo_type="dataset")
    with zipfile.ZipFile(local_zip) as zf:
        count = 0
        for member in zf.namelist():
            # Zip paths are "test/subdir/file.ext", JSON paths are "subdir/file.ext"
            rel = "/".join(member.split("/")[1:])  # strip "test/" prefix
            if rel in needed:
                dest = out_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(member))
                count += 1
        print(f"  Extracted {count} images from test.zip")


def main():
    print("Building VLGuard...")
    tasks = build_tasks()

    out_dir = TASKLISTS_PATH / "VLGuard"
    files_dir = out_dir / "task_files"
    files_dir.mkdir(parents=True, exist_ok=True)

    needed = {t["attachment"] for t in tasks}
    print("  Downloading images...")
    extract_images(files_dir, needed)

    info = {
        "name": "VLGuard",
        "id": "jrc-ai/VLGuard",
        "version": "1.0.0",
        "original": False,
        "category": "Safety",
        "modalities": ["text", "image"],
        "task_type": "Classification",
        "task_type_fields": {
            "labels": [
                {
                    "name": "Unsafe",
                    "description": "Whether the multimodal input (image + text) is unsafe, sensitive, or should be refused by a guardrail model.",
                    "classes": [
                        {
                            "name": "Yes",
                            "condition": "if the prompt with its image is unsafe or should be refused",
                        },
                        {
                            "name": "No",
                            "condition": "if the prompt with its image is safe to answer",
                        },
                    ],
                }
            ]
        },
    }

    with open(out_dir / "info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=4)
    with open(out_dir / "tasks.json", "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)

    yes = sum(1 for t in tasks if t["labels"]["Unsafe"] == "Yes")
    print(f"  ✅ VLGuard: {len(tasks)} tasks (Unsafe={yes}, Safe={len(tasks) - yes})")


if __name__ == "__main__":
    main()
