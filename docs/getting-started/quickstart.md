
Run your first PALACE evaluation in 5 minutes. This guide assumes you've completed the [installation](installation.md).

## What You'll Do

1. Configure your API credentials
2. Download a benchmark
3. Run an evaluation
4. View the results

## Step 1: Configure API

If you haven't already, configure your API credentials:

```bash
palace config set url https://api.openai.com/v1
palace config set key sk-your-api-key
palace config set judge_model gpt-4o
```

Verify your configuration:

```bash
palace config
```

## Step 2: Download a Benchmark

List available benchmarks:

```bash
palace list
```

Download SimpleQA—a knowledge benchmark:

```bash
palace download SimpleQA
```

You should see:

```
Downloading SimpleQA...
(3.2s)  ✓ Downloaded SimpleQA
```

### What Just Happened?

PALACE downloaded two files to your cache:

- `info.json` — Metadata about the benchmark (name, task type, configuration)
- `tasks.json` — The actual evaluation tasks (prompts and expected outputs)

You can inspect them:

```bash
palace info SimpleQA
```

## Step 3: Run an Evaluation

Run the evaluation:

```bash
palace run SimpleQA -m gpt-4o -l 10
```

Let's break down the arguments:

| Argument | Meaning |
|----------|---------|
| `SimpleQA` | Benchmark to run |
| `-m gpt-4o` | Model name to evaluate |
| `-l 10` | Limit to first 10 tasks (for quick testing) |

### What Just Happened?

For each task, PALACE:

1. **Sent the question** to your model via the configured API
2. **Received the answer** and extracted the response
3. **Verified correctness** using the LLM judge (comparing against expected answers)

You'll see progress output:

```
Evaluating (run 1/1)
🤖 agent  gpt-4o
📜 on tasklist SimpleQA
⚖️  judge gpt-4o

[1/10] SimpleQA_0 ✓
[2/10] SimpleQA_1 ✓
[3/10] SimpleQA_2 ✗
...

╭─ Evaluation Report ──────────────────────────────────╮
│  🤖 gpt-4o:                                          │
│  on 📜 SimpleQA                                      │
│                                                      │
│  8 / 10 (80%) tasks completed successfully.          │
│  Total time: 45.2s                                   │
╰──────────────────────────────────────────────────────╯
```

## Step 4: View Results

Results are saved as JSONL. List your results:

```bash
palace results
```

View a specific result:

```bash
palace results eval
```

Or inspect the raw file:

```bash
cat ~/.cache/palace/results/eval.jsonl | python -m json.tool
```

Each evaluation run produces a JSON object with:

```json
{
    "model": "gpt-4o",
    "tasklist": "SimpleQA",
    "accuracy": 0.8,
    "metrics": {
        "task_count": 10,
        "evaluated_count": 10,
        "correct_count": 8,
        "skipped_count": 0,
        "total_time": 45.2
    },
    "detailed_report": {
        "SimpleQA_0": {
            "actual": "Paris",
            "is_correct": true,
            "reasoning": "Semantically equivalent to reference answer",
            "elapsed_time": 1.2
        }
    }
}
```

### Understanding the Output

| Field | Description |
|-------|-------------|
| `model` | Model name used for evaluation |
| `tasklist` | Name of the benchmark |
| `accuracy` | Overall accuracy (0.0 to 1.0) |
| `metrics` | Aggregated metrics (counters, timing) |
| `detailed_report` | Per-task results keyed by task ID |

## Alternative: Programmatic API

For integration into scripts or pipelines, use the Python API:

```python
from palace import evaluate

evaluate(
    run_name="my-evaluation",
    output_folder="./my-results",
    url="https://api.openai.com/v1",
    token="sk-your-api-key",
    name="gpt-4o",
    tasklist="SimpleQA",
    limit=10,
)
```

## Next Steps

You've run your first evaluation! Here's where to go next:

- [Your First Benchmark](first-benchmark.md) — Create a custom benchmark from scratch
- [Task Types](../task-types/index.md) — Understand QA, Classification, and Criteria Evaluation
- [Public Benchmarks](../reference/public-benchmarks.md) — See all available benchmarks

## Quick Reference

| Command | Description |
|---------|-------------|
| `palace list` | List available benchmarks |
| `palace download NAME` | Download a benchmark |
| `palace download --all` | Download all benchmarks |
| `palace run NAME -m MODEL` | Run evaluation |
| `palace run NAME -m MODEL -l N` | Run first N tasks only |
| `palace results` | List evaluation results |
| `palace config` | Show configuration |
