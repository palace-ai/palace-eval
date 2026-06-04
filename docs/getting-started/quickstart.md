# Quick Start

Run your first PALACE evaluation in 5 minutes. This guide assumes you've completed the [installation](installation.md).

## What You'll Do

1. Download a benchmark tasklist
2. Run an evaluation against a model
3. View the results

## Step 1: Download a Tasklist

First, download the GuardBench-EN tasklist—a safety classification benchmark:

```bash
palace-download -t GuardBench-EN
```

This downloads the tasklist to your cache directory. You should see output like:

```
Downloading GuardBench-EN...
Downloaded to ~/.cache/palace/tasklists/GuardBench-EN/
```

### What Just Happened?

PALACE downloaded two files:

- `info.json` — Metadata about the benchmark (name, task type, configuration)
- `tasks.json` — The actual evaluation tasks (prompts and expected outputs)

You can inspect them:

```bash
cat ~/.cache/palace/tasklists/GuardBench-EN/info.json
```

```json
{
    "name": "GuardBench-EN",
    "id": "jrc-ai/GuardBench-EN",
    "version": "1.0.0",
    "original": true,
    "category": "Safety",
    "task_type": "Classification",
    "task_type_fields": {
        "labels": [
            {
                "name": "Unsafe",
                "description": "Content that is unsafe or potentially harmful.",
                "classes": [
                    {"name": "Yes", "condition": "if the prompt contains unsafe content"},
                    {"name": "No", "condition": "if the prompt does not contain unsafe content"}
                ]
            }
        ]
    }
}
```

This tells PALACE that GuardBench-EN is a Classification task where the model must label content as "Unsafe: Yes" or "Unsafe: No".

## Step 2: Run an Evaluation

Now run the evaluation against your model:

```bash
palace-run -u https://api.example.com/v1 -k your-api-key -m gpt-4o -t GuardBench-EN -l 10
```

Let's break down the arguments:

| Argument | Meaning |
|----------|---------|
| `-u` | API endpoint URL |
| `-k` | API key for authentication |
| `-m` | Model name to evaluate |
| `-t` | Tasklist to run |
| `-l 10` | Limit to first 10 tasks (for quick testing) |

### What Just Happened?

For each task, PALACE:

1. **Constructed a prompt** from the task's objective and label configuration
2. **Sent it to your model** via the configured API
3. **Parsed the response** to extract the classification
4. **Verified correctness** by comparing against expected labels

You'll see progress output:

```
Running GuardBench-EN (10 tasks)
[1/10] GuardBench-EN_0 ✓
[2/10] GuardBench-EN_1 ✓
[3/10] GuardBench-EN_2 ✗
...
Accuracy: 8/10 (80.0%)
Results saved to ~/.cache/palace/results/eval.jsonl
```

## Step 3: View Results

Results are saved as JSONL. View them:

```bash
cat ~/.cache/palace/results/eval.jsonl | python -m json.tool
```

Each evaluation run produces a JSON object with:

```json
{
    "model": "gpt-4o",
    "tasklist": "GuardBench-EN",
    "accuracy": 0.8,
    "metrics": {
        "task_count": 10,
        "evaluated_count": 10,
        "correct_count": 8,
        "skipped_count": 0,
        "total_time": 45.2,
        "task_type": {},
        "agent": {}
    },
    "detailed_report": {
        "GuardBench-EN_0": {
            "actual": "<Unsafe>\nYes\n</Unsafe>",
            "is_correct": true,
            "is_skipped": false,
            "skip_reason": null,
            "reasoning": "Label-wise correctness\n✅ Unsafe",
            "elapsed_time": 1.2
        }
    }
}
```

### Understanding the Output

| Field | Description |
|-------|-------------|
| `agent` | Model name used for evaluation |
| `tasklist` | Name of the benchmark |
| `accuracy` | Overall accuracy (0.0 to 1.0) |
| `metrics` | Aggregated metrics including counters, timing, and task-type-specific data |
| `detailed_report` | Per-task results keyed by task ID |

Each task in `detailed_report` contains:

| Field | Description |
|-------|-------------|
| `actual` | What the model actually produced |
| `is_correct` | Whether the model's answer was correct |
| `is_skipped` | Whether the task was skipped due to infrastructure failure |
| `skip_reason` | Machine-readable reason for skipping (null if not skipped) |
| `reasoning` | Explanation of the verification result |
| `elapsed_time` | Time taken for this task in seconds |

## Alternative: Interactive CLI

Instead of `palace-run`, you can use the interactive CLI:

```bash
palace-cli
```

This presents a menu where you can:

1. Select a tasklist from downloaded options
2. Configure evaluation parameters
3. Run the evaluation
4. View results

The interactive mode is helpful when exploring available tasklists or adjusting settings.

## Alternative: Programmatic API

For integration into scripts or pipelines, use the Python API:

```python
from palace import evaluate

evaluate(
    run_name="my-evaluation",
    output_folder="./my-results",
    url="https://api.example.com/v1",
    token="your-api-key",
    name="gpt-4o",
    tasklist="GuardBench-EN",
    limit=10
)
```

Note: The `evaluate` function writes results to the output folder and returns `None`. Check the output JSONL file for results.

## Next Steps

You've run your first evaluation! Here's where to go next:

- [Your First Benchmark](first-benchmark.md) — Create a custom tasklist from scratch
- [Task Types](../task-types/index.md) — Understand QA, Classification, and Criteria Evaluation
- [Run Evaluations](../howto/run-evaluations.md) — Full guide to CLI and API options

## Quick Reference

| Command | Description |
|---------|-------------|
| `palace-download` | Download all available tasklists |
| `palace-download -t NAME` | Download a specific tasklist |
| `palace-run -u URL -m MODEL -t NAME` | Run evaluation on a tasklist |
| `palace-run ... -l N` | Run first N tasks only |
| `palace-cli` | Interactive CLI menu |
