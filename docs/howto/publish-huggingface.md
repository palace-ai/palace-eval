# How to Publish to HuggingFace

This guide explains how to publish your PALACE tasklist to HuggingFace, making it available for others to download and use.

## Prerequisites

- A working PALACE tasklist (tested locally)
- A HuggingFace account
- The `huggingface_hub` library installed (`pip install huggingface_hub`)

## Step 1: Prepare Your Tasklist

Ensure your tasklist is complete and tested:

```bash
# Verify the tasklist works
palace-run -u https://api.example.com/v1 -m gpt-4o -t MyBenchmark -l 5
```

Your tasklist directory should contain:

```
MyBenchmark/
├── info.json      # Required: metadata and configuration
└── tasks.json     # Required: evaluation tasks
```

### info.json Requirements

Your `info.json` must include:

```json
{
    "name": "MyBenchmark",
    "id": "your-username/MyBenchmark",
    "version": "1.0.0",
    "category": "Your Category",
    "task_type": "QA"
}
```

| Field | Description |
|-------|-------------|
| `name` | Display name for the benchmark |
| `id` | HuggingFace dataset ID (username/name format) |
| `version` | Semantic version (major.minor.patch) |
| `category` | Grouping category |
| `task_type` | One of: QA, Classification, Report Generation |

## Step 2: Authenticate with HuggingFace

Log in to HuggingFace:

```bash
huggingface-cli login
```

Enter your HuggingFace token when prompted. You can create a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).

## Step 3: Create the Dataset Repository

Create a new dataset on HuggingFace:

```bash
huggingface-cli repo create MyBenchmark --type dataset
```

Or create it via the HuggingFace web interface at [huggingface.co/new-dataset](https://huggingface.co/new-dataset).

## Step 4: Upload Your Tasklist

Upload your files to the repository:

```python
from huggingface_hub import HfApi

api = HfApi()

# Upload info.json
api.upload_file(
    path_or_fileobj="~/.cache/palace/tasklists/MyBenchmark/info.json",
    path_in_repo="info.json",
    repo_id="your-username/MyBenchmark",
    repo_type="dataset"
)

# Upload tasks.json
api.upload_file(
    path_or_fileobj="~/.cache/palace/tasklists/MyBenchmark/tasks.json",
    path_in_repo="tasks.json",
    repo_id="your-username/MyBenchmark",
    repo_type="dataset"
)
```

Or use the CLI:

```bash
cd ~/.cache/palace/tasklists/MyBenchmark
huggingface-cli upload your-username/MyBenchmark . --repo-type dataset
```

## Step 5: Add a README

Create a `README.md` for your dataset:

```markdown
---
license: mit
task_categories:
  - text-classification
language:
  - en
tags:
  - palace
  - benchmark
  - evaluation
---

# MyBenchmark

A PALACE benchmark for evaluating [describe what it tests].

## Usage

Download with PALACE:

```bash
palace-download -t MyBenchmark
```

Run evaluation:

```bash
palace-run -u https://api.example.com/v1 -m gpt-4o -t MyBenchmark
```

## Task Type

This benchmark uses the **QA** task type with [describe configuration].

## Statistics

- **Tasks**: 100
- **Category**: Knowledge
- **Difficulty**: Mixed

## Citation

If you use this benchmark, please cite:

```bibtex
@misc{mybenchmark2026,
  title={MyBenchmark: A benchmark for...},
  author={Your Name},
  year={2026}
}
```
```

Upload the README:

```bash
huggingface-cli upload your-username/MyBenchmark README.md --repo-type dataset
```

## Step 6: Verify the Upload

Check that your dataset is accessible:

1. Visit `https://huggingface.co/datasets/your-username/MyBenchmark`
2. Verify both `info.json` and `tasks.json` are present
3. Test downloading:

```bash
palace-download -t your-username/MyBenchmark
```

## Adding to the PALACE Collection

To have your benchmark included in the official PALACE collection:

1. Ensure your benchmark follows PALACE conventions
2. Test thoroughly with multiple models
3. Open an issue or pull request on the PALACE repository
4. Include documentation about what the benchmark evaluates

## Best Practices

### Versioning

Use semantic versioning:

- **Major** (1.0.0 → 2.0.0): Breaking changes to task format
- **Minor** (1.0.0 → 1.1.0): New tasks added
- **Patch** (1.0.0 → 1.0.1): Bug fixes, typo corrections

### Documentation

Include in your README:

- What capability the benchmark tests
- How to interpret results
- Any special configuration needed
- Citation information

### Quality Checks

Before publishing:

- [ ] All tasks have unique IDs
- [ ] JSON is valid and well-formatted
- [ ] Expected values are accurate
- [ ] Benchmark runs successfully with `palace-run`
- [ ] Results are meaningful (not all pass or all fail)

---

## Related Pages

- [Your First Benchmark](../getting-started/first-benchmark.md) — Creating a tasklist
- [Task Types](../task-types/index.md) — Understanding task type configuration
- [info.json Reference](../reference/info-json.md) — Complete field specification
