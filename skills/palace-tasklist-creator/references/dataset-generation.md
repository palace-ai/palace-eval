# Dataset Generation Guide

How to create palace tasklists from existing data sources.

## Path 1: palace-download (HuggingFace Datasets)

If your benchmark is available on HuggingFace, use `palace-download` with column mapping. This is the fastest path — it handles streaming, progress, and file extraction automatically.

### How It Works

The `download_tasklist()` function:
1. Streams the HuggingFace dataset (row by row)
2. Maps HuggingFace columns to palace fields using `column_names`
3. Extracts attachments (images, text files) to `task_files/`
4. Writes `info.json` + `tasks.json` to `~/.cache/palace/tasklists/{name}/`

### Configuration Format (public_datasets_info.json)

Each entry in the download registry:

```json
{
  "name": "MyBenchmark",
  "id": "org/dataset-name",
  "config": "default",
  "split": "test",
  "column_names": {
    "id": "id",
    "objective": "question",
    "expected": "answer",
    "difficulty": "level",
    "attachment": "image"
  },
  "category": "Reasoning",
  "task_type": "QA"
}
```

### column_names Mapping

Maps palace field names (keys) to HuggingFace column names (values):

| Palace Field | Description | Example HF Column |
|-------------|-------------|-------------------|
| `id` | Task identifier | `"id"`, `"idx"` |
| `objective` | The prompt/question | `"question"`, `"prompt"`, `"input"` |
| `expected` | Expected answer | `"answer"`, `"target"`, `"gt"` |
| `difficulty` | Difficulty level | `"level"`, `"difficulty_level"` |
| `attachment` | Single attachment column | `"image"`, `"document"` |
| `attachments` | Multiple attachment columns | `["image", "context_doc"]` |

If a column name matches the palace field name, you can omit it from `column_names`.

### Additional Options

| Field | Type | Description |
|-------|------|-------------|
| `inline_attachment` | boolean | If `true`, text attachments are saved as files in `task_files/` rather than kept inline |
| `keep_custom_columns` | boolean | Keep HuggingFace columns not mapped to palace fields (goes to `custom_fields`) |
| `task_type_fields` | object | Task type configuration (same as info.json) |
| `default_labels` | dict | Default label values for Classification |
| `label_mapping` | dict | Map HuggingFace label values to palace class names |
| `custom_verificator` | string | Python function string for custom verification |

### Multi-Split Datasets

```json
{
  "name": "BABILong-32k",
  "id": "RMT-team/babilong",
  "config": "32k",
  "split": ["qa1", "qa2", "qa3", "qa4", "qa5"],
  "column_names": {"objective": "question", "expected": "target", "attachments": "input"},
  "inline_attachment": true,
  "task_type": "QA"
}
```

### Custom Verificator via Download

```json
{
  "name": "ProteinBench",
  "id": "org/protein-bench",
  "split": "train",
  "column_names": {"objective": "prompt", "expected": "gt"},
  "task_type": "QA",
  "custom_verificator": "def verify(pred, truth):\n    import json\n    return pred == json.loads(truth)['sequence']"
}
```

### Dynamic Classes (Classification from HF)

For multiple-choice datasets where options vary per task, use `classes_from` in `task_type_fields`:

```json
{
  "task_type": "Classification",
  "task_type_fields": {
    "labels": [
      {
        "name": "Answer",
        "description": "The correct answer",
        "classes_from": {
          "from_column": "choices",
          "class_naming": "letters"
        }
      }
    ]
  }
}
```

This generates `A`, `B`, `C`, `D` classes from the items in the `choices` column.

---

## Path 2: create_dataset.py (Custom Script)

For benchmarks not on HuggingFace, or when you need custom processing logic.

### Location Convention

```
palace-eval/src/palace/data_utils/{benchmark_name}_dataset/
├── __init__.py           # Empty
├── create_dataset.py     # Generator script
└── (source data files)   # Optional: local data
```

### Minimal Template

```python
import json
from pathlib import Path
from palace.utils.paths import TASKLISTS_PATH

TASKLIST_NAME = "My-Benchmark"

# Load your source data
source_data = load_your_data()  # however you get it

# Convert to palace format
tasks = []
for i, item in enumerate(source_data):
    tasks.append(
        {
            "id": f"{TASKLIST_NAME}_{i}",
            "objective": item["question"],
            "expected": item["answer"],
        }
    )

# Write outputs
out_dir = TASKLISTS_PATH / TASKLIST_NAME
out_dir.mkdir(parents=True, exist_ok=True)

with open(out_dir / "tasks.json", "w", encoding="utf-8") as f:
    json.dump(tasks, f, indent=2)

info = {
    "name": TASKLIST_NAME,
    "task_type": "QA",
    "category": "My Category",
    "input_modalities": ["text"],
    "output_modalities": ["text"],
}
with open(out_dir / "info.json", "w", encoding="utf-8") as f:
    json.dump(info, f, indent=2)

print(f"Created {len(tasks)} tasks in {out_dir}")
```

### Classification Example (GuardBench pattern)

```python
import json
from pathlib import Path
import pandas as pd
from palace.utils.paths import TASKLISTS_PATH

TASKLIST_NAME = "My-Safety-Bench"

# Load from JSONL
df = pd.read_json(Path(__file__).parent / "prompts.jsonl", lines=True)
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

tasks = []
for i, row in df.iterrows():
    tasks.append(
        {
            "id": f"{TASKLIST_NAME}_{i}",
            "objective": row["text"],
            "labels": {"Unsafe": "Yes" if row["label"] else "No"},
        }
    )

info = {
    "name": TASKLIST_NAME,
    "id": f"org/{TASKLIST_NAME}",
    "version": "1.0.0",
    "original": True,
    "category": "Safety",
    "task_type": "Classification",
    "task_type_fields": {
        "labels": [
            {
                "name": "Unsafe",
                "description": "Whether the content is unsafe.",
                "classes": [
                    {"name": "Yes", "condition": "if unsafe"},
                    {"name": "No", "condition": "if safe"},
                ],
            }
        ]
    },
}

out_dir = TASKLISTS_PATH / TASKLIST_NAME
out_dir.mkdir(parents=True, exist_ok=True)
json.dump(tasks, open(out_dir / "tasks.json", "w"), indent=2)
json.dump(info, open(out_dir / "info.json", "w"), indent=2)
```

### Agentic Example (SWE-bench pattern)

```python
import json, shutil
from pathlib import Path
from datasets import load_dataset
from palace.utils.paths import TASKLISTS_PATH

TASKLIST_NAME = "My-Code-Bench"

ds = load_dataset("org/code-bench", split="test")
out_dir = TASKLISTS_PATH / TASKLIST_NAME
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "task_files").mkdir(exist_ok=True)

tasks = []
envs = {}
for item in ds:
    env_name = item["docker_tag"]
    if env_name not in envs:
        envs[env_name] = {
            "image": f"registry/{env_name}",
            "tools": ["bash", "read", "write", "edit", "grep", "glob", "ls"],
            "resources": {"memory": "8g", "cpus": 2.0, "network": True},
        }

    task_id = item["instance_id"]
    tasks.append(
        {
            "id": task_id,
            "task_type": "Agentic",
            "objective": item["problem_statement"],
            "env": env_name,
            "seed_args": {"base_commit": item["base_commit"], "problem_statement": item["problem_statement"]},
            "expected_outcome": {"fail_to_pass": item["fail_to_pass"], "pass_to_pass": item["pass_to_pass"]},
        }
    )

info = {
    "name": TASKLIST_NAME,
    "task_type": "Agentic",
    "category": "Code Generation",
    "input_modalities": ["text"],
    "output_modalities": ["text"],
    "env": envs,
}

json.dump(tasks, open(out_dir / "tasks.json", "w"), indent=2)
json.dump(info, open(out_dir / "info.json", "w"), indent=2)

# Copy environment scripts
env_dir = out_dir / "environment"
env_dir.mkdir(exist_ok=True)
shutil.copy("seed.py", env_dir / "seed.py")
shutil.copy("verify.py", env_dir / "verify.py")
```

---

## Multimodal Handling

### Image Attachments

1. Set `"input_modalities": ["image", "text"]` in info.json
2. Save images in `task_files/` (e.g., `task_files/img_001.png`)
3. Reference in task: `"attachment": "img_001.png"`

Images are sent as multimodal content (base64-encoded) to models that support vision.

### Inline Text Attachments

For long documents that should be prepended to the prompt:

1. Save text files in `task_files/` (e.g., `task_files/context_001.txt`)
2. Reference in task: `"attachment": "context_001.txt"`

Text extensions (`.txt`, `.md`, `.json`, `.py`, `.csv`, etc.) are read and prepended to the objective automatically.

### Inline Attachment via palace-download

Set `"inline_attachment": true` in the download config. The content from the specified column will be saved as individual text files in `task_files/` and referenced via `attachments`.

---

## Running Your Generator

```bash
cd palace-eval
python -m palace.data_utils.my_benchmark_dataset.create_dataset
```

Or if standalone:
```bash
python create_dataset.py
```

Output goes to `~/.cache/palace/tasklists/{name}/`. Verify with:
```bash
python .kiro/skills/palace-tasklist-creator/scripts/validate_tasklist.py ~/.cache/palace/tasklists/{name}
```
