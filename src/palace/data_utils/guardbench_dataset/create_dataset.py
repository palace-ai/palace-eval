import json
from pathlib import Path

import pandas as pd
from palace.utils.paths import TASKLISTS_PATH

gb_datasets_to_palace_mapping = {
    "prompts_de": "GuardBench-DE",
    "prompts_en": "GuardBench-EN",
    "prompts_es": "GuardBench-ES",
    "prompts_fr": "GuardBench-FR",
    "prompts_it": "GuardBench-IT",
}

# Create a merged dataframe with id as index and text_{language code} as columns
df_merged = pd.DataFrame()
for file in Path(__file__).parent.glob("*.jsonl"):
    if file.stem not in gb_datasets_to_palace_mapping:
        continue
    df = (
        pd.read_json(file, encoding="utf-8", lines=True)
        .rename(columns={"text": f"text_{file.stem}"})
        .set_index("id")
    )
    if df_merged.empty:
        df_merged = df
    else:
        # merge on id, adding only the new text column
        df_merged = pd.concat([df_merged, df[df.columns[1:]]], axis=1, join="outer")

# Shuffle merged_df rows
df_merged = df_merged.sample(frac=1, random_state=42).reset_index(drop=True)

# Convert dataframe to palace format and save to json files
tasks = {lang: [] for lang in gb_datasets_to_palace_mapping}
for i, row in enumerate(df_merged.itertuples()):
    print(f"Processing row {i + 1}/{len(df_merged)}...", end="\r", flush=True)
    for lang in gb_datasets_to_palace_mapping:
        tasks[lang].append(
            {
                "id": f"{gb_datasets_to_palace_mapping[lang]}_{i}",
                "objective": getattr(row, f"text_{lang}"),
                "labels": {"Unsafe": "Yes" if row.label is True else "No"},
                "expected": "Unsafe" if row.label is True else "Safe",  # useless
            }
        )

info = {
    lang: {
        "name": gb_datasets_to_palace_mapping[lang],
        "id": f"jrc-ai/{gb_datasets_to_palace_mapping[lang]}",
        "version": "1.0.0",
        "original": True,
        "category": "Safety",
        "task_type": "Classification",
        "task_type_fields": {
            "labels": [
                {
                    "name": "Unsafe",
                    "description": "Content that is unsafe or potentially harmful.",
                    "classes": [
                        {
                            "name": "Yes",
                            "condition": "if the prompt contains unsafe content",
                        },
                        {
                            "name": "No",
                            "condition": "if the prompt does not contain unsafe content",
                        },
                    ],
                }
            ]
        },
    }
    for lang in gb_datasets_to_palace_mapping
}

for lang in gb_datasets_to_palace_mapping:
    Path(TASKLISTS_PATH / gb_datasets_to_palace_mapping[lang]).mkdir(
        parents=True, exist_ok=True
    )
    json.dump(
        tasks[lang],
        open(
            TASKLISTS_PATH / gb_datasets_to_palace_mapping[lang] / "tasks.json",
            "w",
            encoding="utf-8",
        ),
        indent=4,
    )
    json.dump(
        info[lang],
        open(
            TASKLISTS_PATH / gb_datasets_to_palace_mapping[lang] / "info.json",
            "w",
            encoding="utf-8",
        ),
        indent=4,
    )
