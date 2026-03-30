"""
Convert MMInstruction/RedTeamingVLM to PALACE Classification tasklists.

Produces three tasklist variants:
  - RTVLM-Strict:  "Proceed with Caution" → Unsafe=Yes
  - RTVLM-Lenient: "Proceed with Caution" → Unsafe=No
  - RTVLM-Binary:  "Proceed with Caution" samples excluded

Both map "Refuse to Answer" → Unsafe=Yes and "Safe to Answer" → Unsafe=No.

Source: https://huggingface.co/datasets/MMInstruction/RedTeamingVLM

Included subsets (6):
  celebrity_mixed (200) - Mixed celebrities/ordinary people, 50/50 refuse/caution
  misleading      (100) - Leading questions with misleading images, 3-way split
  jailbreak       (200) - Jailbreak via images, all "Refuse to Answer"
  jailbreak2       (21) - Additional jailbreaks, shares images with jailbreak
  politics        (200) - Politically sensitive images, all "Proceed with Caution"
  racial          (200) - Racially sensitive images, all "Proceed with Caution"

Excluded subsets:
  captcha          - No safety label; tests captcha-solving ability
  celebrity_full   - All 1000 entries same label ("Answer with Caution"), no binary signal
  face             - All 2040 entries same label, tests fairness/bias not safety
  visual_misleading_wrong/correct - All "Safe to Answer", tests factual QA not safety
  visual_order_a/b - All "Safe to Answer", multi-image (unsupported), tests reasoning
"""

import json
import random
import zipfile
from pathlib import Path

from huggingface_hub import hf_hub_download
from palace.utils.paths import TASKLISTS_PATH

REPO_ID = "MMInstruction/RedTeamingVLM"

# (id_prefix, img_prefix, jsonl_path, question_key, rta_key, img_key, img_ext, zip_path)
SUBSETS = [
    (
        "celeb",
        "celeb",
        "data/Celebrity/mixed.jsonl",
        "prompt",
        "refused_to_answer",
        "id",
        "",
        "data/Celebrity/mix.zip",
    ),
    (
        "mislead",
        "mislead",
        "data/Harmful/misleading.jsonl",
        "questions",
        "refused_to_answer",
        "index",
        ".jpg",
        "data/Harmful/img/img.zip",
    ),
    (
        "jb",
        "jb",
        "data/Jailbreak/jailbreak.jsonl",
        "instruction",
        "refused_to_answer",
        "index",
        ".jpg",
        "data/Jailbreak/img/img.zip",
    ),
    (
        "jb2",
        "jb",
        "data/Jailbreak2/jailbreak.jsonl",
        "instruction",
        "refused_to_answer",
        "index",
        ".jpg",
        "data/Jailbreak/img/img.zip",
    ),
    (
        "politics",
        "politics",
        "data/Safety/Politics/politics.jsonl",
        "prompt",
        "refused_to_answer",
        "id",
        "",
        "data/Safety/Politics/img/politics.zip",
    ),
    (
        "racial",
        "racial",
        "data/Safety/Racial/racial.jsonl",
        "prompt",
        "refused_to_answer",
        "id",
        "",
        "data/Safety/Racial/img/racial.zip",
    ),
]

FIXED_LABELS = {"Refuse to Answer": "Yes", "Safe to Answer": "No"}


def load_jsonl(path: str) -> list[dict]:
    local = hf_hub_download(REPO_ID, path, repo_type="dataset")
    with open(local, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def extract_all_images(out_dir: Path, needed: set[str]) -> None:
    """Download and extract only needed images from subset zips into out_dir."""
    seen_zips = set()
    for _, img_prefix, _, _, _, _, _, zip_path in SUBSETS:
        if (zip_path, img_prefix) in seen_zips:
            continue
        seen_zips.add((zip_path, img_prefix))

        local_zip = hf_hub_download(REPO_ID, zip_path, repo_type="dataset")
        with zipfile.ZipFile(local_zip) as zf:
            count = 0
            for member in zf.namelist():
                name = Path(member).name
                prefixed = f"{img_prefix}_{name}"
                if name and prefixed in needed:
                    (out_dir / prefixed).write_bytes(zf.read(member))
                    count += 1
            print(f"  Extracted {count} images from {zip_path}")


def build_tasks(caution_label: str | None) -> list[dict]:
    """Build tasks. caution_label=None skips "Proceed with Caution" samples."""
    tasks = []

    for id_prefix, img_prefix, jsonl, q_key, rta_key, img_key, img_ext, _ in SUBSETS:
        for i, row in enumerate(load_jsonl(jsonl)):
            question = row[q_key]
            if isinstance(question, list):
                question = question[0]

            rta = row[rta_key]
            if isinstance(rta, list):
                rta = rta[0]

            if rta == "Proceed with Caution":
                if caution_label is None:
                    continue
                label = caution_label
            else:
                label = FIXED_LABELS[rta]

            tasks.append(
                {
                    "id": f"RTVLM_{id_prefix}_{i}",
                    "objective": question,
                    "attachment": f"{img_prefix}_{row[img_key]}{img_ext}",
                    "labels": {"Unsafe": label},
                }
            )

    random.Random(42).shuffle(tasks)
    return tasks


def save_tasklist(name: str, tasks: list[dict]) -> None:
    out_dir = TASKLISTS_PATH / name
    files_dir = out_dir / "task_files"
    files_dir.mkdir(parents=True, exist_ok=True)

    needed = {t["attachment"] for t in tasks}

    print("  Downloading images...")
    extract_all_images(files_dir, needed)

    info = {
        "name": name,
        "id": f"jrc-ai/{name}",
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
    print(f"  ✅ {name}: {len(tasks)} tasks (Unsafe={yes}, Safe={len(tasks) - yes})")


def main():
    print("Building RTVLM-Strict (Proceed with Caution → Unsafe)...")
    save_tasklist("RTVLM-Strict", build_tasks(caution_label="Yes"))

    print("\nBuilding RTVLM-Lenient (Proceed with Caution → Safe)...")
    save_tasklist("RTVLM-Lenient", build_tasks(caution_label="No"))

    print("\nBuilding RTVLM-Binary (Proceed with Caution excluded)...")
    save_tasklist("RTVLM-Binary", build_tasks(caution_label=None))


if __name__ == "__main__":
    main()
