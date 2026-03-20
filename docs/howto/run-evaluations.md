# How to Run Evaluations

This guide covers all the ways to run PALACE evaluations: interactive CLI, command-line interface, and programmatic API.

## Prerequisites

- PALACE installed ([Installation Guide](../getting-started/installation.md))
- API credentials configured
- At least one tasklist downloaded (`palace-download`)

## Method 1: Interactive CLI

The interactive CLI provides a menu-driven interface for running evaluations.

```bash
palace-cli
```

You'll see a menu with options to:

1. Select a tasklist from downloaded options
2. Configure evaluation parameters
3. Run the evaluation
4. View results

**Best for**: Exploring available tasklists, one-off evaluations, learning PALACE.

## Method 2: Command-Line Interface

The `palace-run` command runs evaluations directly from the terminal.

### Basic Usage

```bash
palace-run --tasklist GuardBench-EN
```

### Common Options

```bash
# Limit number of tasks (useful for testing)
palace-run --tasklist GuardBench-EN --limit 10

# Specify output directory
palace-run --tasklist GuardBench-EN --output ./my-results

# Use a specific model endpoint
palace-run --tasklist GuardBench-EN \
    --model-url https://api.example.com/v1 \
    --model-token your-api-key

# Specify the model name
palace-run --tasklist GuardBench-EN --model gpt-4o
```

### All Options

| Option | Description | Default |
|--------|-------------|---------|
| `--tasklist` | Name of the tasklist to run | Required |
| `--limit` | Maximum number of tasks to run | All tasks |
| `--output` | Output directory for results | `~/.cache/palace/results/` |
| `--model-url` | API endpoint URL | From environment |
| `--model-token` | API authentication token | From environment |
| `--model` | Model name to use | From environment |
| `--verbose` | Enable detailed logging | False |

**Best for**: Scripted evaluations, CI/CD pipelines, batch processing.

## Method 3: Programmatic API

For integration into Python scripts and applications, use the `evaluate` function.

### Basic Usage

```python
from palace import evaluate

results = evaluate(
    tasklist="GuardBench-EN",
    model_url="https://api.example.com/v1",
    model_token="your-api-key"
)

print(f"Accuracy: {results.accuracy:.1%}")
```

### With Options

```python
from palace import evaluate

results = evaluate(
    tasklist="GuardBench-EN",
    model_url="https://api.example.com/v1",
    model_token="your-api-key",
    output_path="./my-results",
    limit=10,
    model="gpt-4o"
)

# Access detailed results
for task_result in results.task_results:
    print(f"{task_result.task_id}: {'✓' if task_result.is_correct else '✗'}")
```

### Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `tasklist` | str | Name of the tasklist | Required |
| `model_url` | str | API endpoint URL | From environment |
| `model_token` | str | API authentication token | From environment |
| `output_path` | str | Output directory | `~/.cache/palace/results/` |
| `limit` | int | Maximum tasks to run | None (all) |
| `model` | str | Model name | From environment |

### Return Value

The `evaluate` function returns a `Results` object with:

```python
results.accuracy        # Float: overall accuracy (0.0 to 1.0)
results.total_tasks     # Int: number of tasks evaluated
results.correct_tasks   # Int: number of correct tasks
results.task_results    # List: detailed per-task results
results.output_file     # Path: location of JSONL results file
```

**Best for**: Custom pipelines, integration with other tools, programmatic analysis.

## Batch Evaluations

### Running Multiple Tasklists

**CLI approach**:
```bash
for tasklist in GuardBench-EN Sycophancy-Binary DocRetrieval-ai; do
    palace-run --tasklist $tasklist --output ./batch-results
done
```

**Python approach**:
```python
from palace import evaluate

tasklists = ["GuardBench-EN", "Sycophancy-Binary", "DocRetrieval-ai"]

for tasklist in tasklists:
    results = evaluate(
        tasklist=tasklist,
        model_url="https://api.example.com/v1",
        model_token="your-api-key",
        output_path="./batch-results"
    )
    print(f"{tasklist}: {results.accuracy:.1%}")
```

### Comparing Models

```python
from palace import evaluate

models = [
    ("gpt-4o", "https://api.openai.com/v1", "key1"),
    ("claude-3", "https://api.anthropic.com/v1", "key2"),
]

for model_name, url, token in models:
    results = evaluate(
        tasklist="GuardBench-EN",
        model_url=url,
        model_token=token,
        model=model_name,
        output_path=f"./results/{model_name}"
    )
    print(f"{model_name}: {results.accuracy:.1%}")
```

## Understanding Output

### Results File

Results are saved as JSONL (one JSON object per line):

```bash
cat ~/.cache/palace/results/GuardBench-EN_2026-03-20_15-00-00.jsonl
```

### Result Structure

Each line contains:

```json
{
    "task_id": "GuardBench-EN_0",
    "objective": "The prompt that was evaluated",
    "expected": "The expected output",
    "model_output": "What the model produced",
    "is_correct": true,
    "reasoning": "Explanation of the verification result",
    "metrics": {
        "criterion": "semantic equivalence"
    }
}
```

### Analyzing Results

```python
import json

# Load results
with open("results.jsonl") as f:
    results = [json.loads(line) for line in f]

# Calculate accuracy
correct = sum(1 for r in results if r["is_correct"])
print(f"Accuracy: {correct}/{len(results)} ({correct/len(results):.1%})")

# Find failures
failures = [r for r in results if not r["is_correct"]]
for f in failures[:5]:
    print(f"\nFailed: {f['task_id']}")
    print(f"Expected: {f['expected']}")
    print(f"Got: {f['model_output']}")
```

## Environment Variables

Configure defaults via environment variables:

```bash
# API configuration
export OPENAI_LIKE_API_BASE_URL=https://api.example.com/v1
export OPENAI_LIKE_API_KEY=your-api-key

# Optional: separate judge configuration
export JUDGE_API_BASE_URL=https://api.example.com/v1
export JUDGE_API_KEY=your-judge-key
export JUDGE_MODEL=gpt-4o
```

With environment variables set, you can run without explicit credentials:

```bash
palace-run --tasklist GuardBench-EN
```

## Troubleshooting

### "Tasklist not found"

Ensure the tasklist is downloaded:

```bash
palace-download --tasklist GuardBench-EN
```

Check available tasklists:

```bash
ls ~/.cache/palace/tasklists/
```

### API Connection Errors

1. Verify your API URL ends with `/v1`
2. Check your API key is valid
3. Test connectivity:

```bash
curl -H "Authorization: Bearer $OPENAI_LIKE_API_KEY" \
     "$OPENAI_LIKE_API_BASE_URL/models"
```

### Rate Limiting

If you hit rate limits:

- Use `--limit` to reduce concurrent requests
- Add delays between evaluations in batch scripts
- Consider using a higher-tier API plan

### Out of Memory

For large tasklists:

- Use `--limit` to process in batches
- Ensure sufficient disk space for results

---

## Related Pages

- [Quick Start](../getting-started/quickstart.md) — Run your first evaluation
- [Debug Evaluations](debug-evaluations.md) — Troubleshooting guide
- [CLI Reference](../reference/cli.md) — Complete command documentation
