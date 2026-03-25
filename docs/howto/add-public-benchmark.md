# Add a Public Benchmark

This guide explains how to add support for a new public HuggingFace benchmark to PALACE's automatic download system.

## Overview

PALACE can automatically convert public HuggingFace datasets into the PALACE tasklist format. The conversion is configured in `public_datasets_info.json`, which maps HuggingFace columns to PALACE task fields.

## Prerequisites

Before adding a benchmark, verify:

1. The dataset is publicly available on HuggingFace
2. It has a clear task structure (question/answer, classification labels, etc.)
3. You understand which columns contain the relevant data

## Step 1: Explore the Dataset

First, examine the dataset on HuggingFace to understand its structure:

```python
from datasets import load_dataset

# Load and inspect
ds = load_dataset("org/dataset-name", split="test")
print(ds.column_names)
print(ds[0])  # First example
```

Identify:

- **Objective column**: The question, prompt, or input text
- **Expected column**: The correct answer or label
- **ID column**: Unique task identifier (optional)
- **Attachment column**: File references or inline content (optional)

## Step 2: Create the Configuration

Add an entry to `public_datasets_info.json`:

### Minimal QA Example

```json
{
  "name": "MyBenchmark",
  "id": "org/dataset-name",
  "split": "test",
  "column_names": {
    "objective": "question",
    "expected": "answer"
  },
  "category": "General Knowledge",
  "task_type": "QA"
}
```

### With All Optional Fields

```json
{
  "name": "MyBenchmark",
  "id": "org/dataset-name",
  "config": "subset_name",
  "split": "validation",
  "column_names": {
    "id": "task_id",
    "objective": "question",
    "expected": "answer",
    "difficulty": "level",
    "attachment": "file_name"
  },
  "attachment_path": "files/validation",
  "category": "Agentic",
  "task_type": "QA"
}
```

## Step 3: Handle Special Cases

### Multiple Splits

If the benchmark has multiple meaningful splits (e.g., difficulty levels):

```json
{
  "name": "BABILong-32k",
  "id": "RMT-team/babilong",
  "config": "32k",
  "split": ["qa1", "qa2", "qa3", "qa4", "qa5"],
  ...
}
```

This creates separate tasklists: `BABILong-32k-qa1`, `BABILong-32k-qa2`, etc.

### Inline Attachments

If attachments are embedded in the dataset (base64 images, inline text):

```json
{
  "column_names": {
    "attachment": "image"
  },
  "inline_attachment": true
}
```

The script automatically detects content type and generates filenames.

### External Attachments

If attachments are separate files in the HuggingFace repo:

```json
{
  "column_names": {
    "attachment": "file_name"
  },
  "attachment_path": "2023/validation"
}
```

### Classification Tasks

For classification benchmarks, define the label schema:

```json
{
  "task_type": "Classification",
  "task_type_fields": {
    "labels": [
      {
        "name": "Sentiment",
        "description": "The emotional tone of the text",
        "classes": [
          {"name": "Positive", "condition": "if the text expresses positive sentiment"},
          {"name": "Negative", "condition": "if the text expresses negative sentiment"},
          {"name": "Neutral", "condition": "if the text has no clear sentiment"}
        ]
      }
    ]
  }
}
```

### Uniform Labels (All Same Class)

For benchmarks where all samples have the same label (e.g., all-unsafe safety benchmarks):

```json
{
  "task_type": "Classification",
  "task_type_fields": {
    "labels": [
      {
        "name": "Unsafe",
        "description": "Whether content is unsafe",
        "classes": [
          {"name": "Yes", "condition": "if unsafe"},
          {"name": "No", "condition": "if safe"}
        ]
      }
    ]
  },
  "default_labels": {
    "Unsafe": "Yes"
  }
}
```

### Label Mapping

If the source dataset uses different label values than you want:

```json
{
  "column_names": {
    "expected": "label"
  },
  "label_mapping": {
    "SUPPORTS": "True",
    "REFUTES": "False",
    "NOT ENOUGH INFO": "Unknown"
  }
}
```

### Custom Verification

For programmatic verification instead of LLM judge:

```json
{
  "custom_verificator": "def verify(pred, truth):\n    import json\n    return pred == json.loads(truth)['answer']"
}
```

The function must:

- Be named `verify`
- Accept `pred` (model output) and `truth` (expected value)
- Return `bool`

## Step 4: Test the Download

Test your configuration:

```bash
palace-download -t MyBenchmark
```

Verify the output:

```bash
# Check info.json
cat ~/.cache/palace/tasklists/MyBenchmark/info.json

# Check first few tasks
head -50 ~/.cache/palace/tasklists/MyBenchmark/tasks.json

# Check attachments (if any)
ls ~/.cache/palace/tasklists/MyBenchmark/task_files/
```

## Step 5: Run a Test Evaluation

Verify the benchmark works end-to-end:

```bash
palace-run -u https://api.example.com/v1 -m gpt-4o -t MyBenchmark -l 5
```

## Configuration Reference

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name and folder name |
| `id` | string | HuggingFace dataset ID |
| `task_type` | string | `QA`, `Classification`, or `Report Generation` |
| `column_names.objective` | string | Column with task prompt |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `config` | string | `"default"` | HuggingFace config/subset |
| `split` | string/array | `"test"` | Dataset split(s) |
| `column_names.expected` | string | — | Column with expected answer |
| `column_names.id` | string | — | Column with task ID |
| `column_names.difficulty` | string | — | Column with difficulty |
| `column_names.attachment` | string | — | Column with attachment |
| `attachment_path` | string | `"task_files"` | Path prefix for files |
| `inline_attachment` | boolean | `false` | Attachment is inline content |
| `category` | string | — | Benchmark category |
| `task_type_fields` | object | — | Task type configuration |
| `default_labels` | object | — | Default labels for all tasks |
| `label_mapping` | object | — | Value transformation map |
| `custom_verificator` | string | — | Python verification function |
| `keep_custom_columns` | boolean | `false` | Preserve extra columns |

---

## Related Pages

- [Public Benchmarks](../reference/public-benchmarks.md) — List of supported benchmarks
- [Task Type Fields](../reference/task-type-fields.md) — Configuration details
- [info.json Reference](../reference/info-json.md) — Tasklist metadata format
