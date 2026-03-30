"""
Convert MM-SafetyBench to PALACE Classification tasklist.

Produces one tasklist: MM-SafetyBench (5,040 tasks over 13 scenarios, all Unsafe=Yes).

Source: https://github.com/isXinLiu/MM-SafetyBench

All prompts are adversarial jailbreak attempts using query-relevant images.
Three image attack types per question:
  - SD: Stable Diffusion generated image of the harmful concept
  - SD_TYPO: SD image with harmful text overlaid as typography
  - TYPO: Plain typography image with harmful text

Prerequisites:
  1. Clone the repo for questions:
       git clone --depth 1 https://github.com/isXinLiu/MM-SafetyBench.git /tmp/MM-SafetyBench
  2. Download images from Google Drive:
       https://drive.google.com/file/d/1xjW9k-aGkmwycqGCXbru70FaSKhSDcR_/view
  3. Unzip into this directory so the structure is:
       mmsafetybench_dataset/
         MM-SafetyBench(imgs)/
           01-Illegal_Activitiy/
             SD/0.jpg, 1.jpg, ...
             SD_TYPO/0.jpg, 1.jpg, ...
             TYPO/0.jpg, 1.jpg, ...
           02-HateSpeech/
           ...
"""

import json
import random
from pathlib import Path

from PIL import Image

from palace.utils.paths import TASKLISTS_PATH

SCRIPT_DIR = Path(__file__).parent
IMGS_DIR = SCRIPT_DIR / "MM-SafetyBench(imgs)"
QUESTIONS_DIR = Path("/tmp/MM-SafetyBench/data/processed_questions")

IMAGE_TYPES = [
    ("SD", "Rephrased Question(SD)"),
    ("SD_TYPO", "Rephrased Question"),
    ("TYPO", "Rephrased Question"),
]


def build_tasks() -> list[dict]:
    tasks = []

    for qfile in sorted(QUESTIONS_DIR.glob("*.json")):
        scenario = qfile.stem  # e.g. "01-Illegal_Activitiy"
        with open(qfile, encoding="utf-8") as f:
            questions = json.load(f)

        for qid, q in questions.items():
            for img_type, q_key in IMAGE_TYPES:
                img_path = f"{scenario}/{img_type}/{qid}.jpg"
                tasks.append(
                    {
                        "id": f"MMSB_{scenario}_{img_type}_{qid}",
                        "objective": q[q_key],
                        "attachment": img_path,
                        "labels": {"Unsafe": "Yes"},
                    }
                )

    random.Random(42).shuffle(tasks)
    return tasks


def main():
    if not IMGS_DIR.exists():
        print(f"Error: {IMGS_DIR} not found. See docstring for download instructions.")
        return
    if not QUESTIONS_DIR.exists():
        print(
            f"Error: {QUESTIONS_DIR} not found. Clone the repo first (see docstring)."
        )
        return

    print("Building MM-SafetyBench...")
    tasks = build_tasks()

    out_dir = TASKLISTS_PATH / "MM-SafetyBench"
    files_dir = out_dir / "task_files"
    files_dir.mkdir(parents=True, exist_ok=True)

    # Copy and compress images (resize to max 512px, JPEG quality 80)
    needed = {t["attachment"] for t in tasks}
    print(f"  Compressing {len(needed)} images...")
    for rel in needed:
        src = IMGS_DIR / rel
        dest = files_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        img = Image.open(src)
        img.thumbnail((512, 512))
        img.save(dest, "JPEG", quality=80)

    info = {
        "name": "MM-SafetyBench",
        "id": "jrc-ai/MM-SafetyBench",
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

    print(f"  ✅ MM-SafetyBench: {len(tasks)} tasks (all Unsafe=Yes)")


if __name__ == "__main__":
    main()
