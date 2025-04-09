import json

from datasets import load_dataset

DATASET_PATH = "gaia-benchmark/GAIA"
DATASET_CONFIG = "2023_all"
TASKLISTS_PATH = "../../tasklists"

ALLOW_INPUT_FILES = False

dataset = load_dataset(DATASET_PATH, DATASET_CONFIG)

dataset.save_to_disk(f"../../data/{DATASET_PATH}")  # is this really needed?
dataset.load_from_disk(f"../../data/{DATASET_PATH}")  # is this completely useless?

df_dataset = dataset["validation"].to_pandas()

# Take only tasks that don't require additional input files
if not ALLOW_INPUT_FILES:
    print("Excluding tasks that require additional input files.")
    df_dataset = df_dataset[
        (df_dataset["file_name"] == "") & (df_dataset["file_path"] == "")
    ]

# Select only useful columns
df_dataset = df_dataset[["Question", "Final answer", "Level"]]

# Convert dataset-specific task format to my own task format
tasks = []
for i, row in df_dataset.iterrows():
    tasks.append(
        {
            "objective": row["Question"],
            "expected": row["Final answer"],
            "difficulty": f"GAIA_Level_{row['Level']}",
        }
    )

# Save tasklist to file
with open(f"{TASKLISTS_PATH}/gaia_tasks.json", "w") as f:
    json.dump(tasks, f, indent=4)

print(f"GAIA tasks successfully saved to {TASKLISTS_PATH}/gaia_tasks.json")
