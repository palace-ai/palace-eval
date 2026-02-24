import json
from pathlib import Path

import pandas as pd
from palace.utils.paths import TASKLISTS_PATH

TASKLIST_NAME = "ValuesEval24"
VALUES_DESCRIPTIONS = {
    "Self-direction": "Independent thought and action—choosing, creating, and exploring.",
    "Stimulation": "Excitement, novelty, and challenge in life.",
    "Hedonism": "Pleasure and sensuous gratification for oneself.",
    "Achievement": "Personal success through demonstrating competence according to social standards.",
    "Power": "Social status and prestige, control or dominance over people and resources.",
    "Face": "Maintenance of one’s public image and avoidance of humiliation.",
    "Security": "Safety, harmony, and stability of society, relationships, and self.",
    "Tradition": "Respect, commitment, and acceptance of the customs and ideas provided by traditional culture or religion.",
    "Conformity": "Restraint of actions, inclinations, and impulses likely to upset others or violate social norms.",
    "Humility": "Recognition of one's insignificance in the larger scheme of things.",
    "Benevolence": "Preservation and enhancement of the welfare of people with whom one is in frequent personal contact.",
    "Universalism": "Understanding, appreciation, tolerance, and protection for the welfare of all people and of nature.",
}

# load the data
labels = pd.read_csv(Path(__file__).parent / "labels.tsv", sep="\t")
sentences = pd.read_csv(Path(__file__).parent / "sentences.tsv", sep="\t")

merged = pd.merge(sentences, labels, on=["Text-ID", "Sentence-ID"], how="inner")

assert len(labels) == len(sentences) == len(merged), (
    "The number of rows in the merged dataset does not match the original datasets."
)

# aggregate columns in merged that are sub-values of the same value
for value in VALUES_DESCRIPTIONS.keys():
    sub_values = [col for col in merged.columns if col.startswith(value)]
    merged[value] = merged[sub_values].max(axis=1)

# keep only the macro-values columns
dataset = merged[["Text-ID", "Sentence-ID", "Text"] + list(VALUES_DESCRIPTIONS.keys())]

# for each sentence, create a task
tasks = []
for idx, row in dataset.iterrows():
    task = {
        "id": f"{TASKLIST_NAME}_{row['Text-ID']}_{row['Sentence-ID']}",
        "objective": row["Text"],
        "labels": {
            value: "Present" if row[value] > 0 else "Absent"
            for value in VALUES_DESCRIPTIONS.keys()
        },
    }
    tasks.append(task)

# save tasks
Path(TASKLISTS_PATH / TASKLIST_NAME).mkdir(parents=True, exist_ok=True)
json.dump(
    tasks,
    open(TASKLISTS_PATH / TASKLIST_NAME / "tasks.json", "w"),
    indent=4,
    ensure_ascii=False,
)

# save metadata
info = {
    "name": TASKLIST_NAME,
    "id": f"jrc-ai/{TASKLIST_NAME}",
    "version": "1.1.0",
    "original": True,
    "config": "default",
    "split": None,
    "category": "MLC",  # new category: Multi-Label Classification
    "category_fields": {  # these fields are compatible with all tasklists of the same category
        "labels": [
            {
                "name": value,
                "description": desc,
                "classes": [
                    {
                        "name": "Present",
                        "condition": "if the value is present in the text",
                    },
                    {
                        "name": "Absent",
                        "condition": "if the value is absent from the text",
                    },
                ],
            }
            for value, desc in VALUES_DESCRIPTIONS.items()
        ]
    },
}
json.dump(
    info,
    open(TASKLISTS_PATH / TASKLIST_NAME / "info.json", "w"),
    indent=4,
    ensure_ascii=False,
)
