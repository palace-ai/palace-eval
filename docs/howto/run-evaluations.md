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
palace-run -u https://api.example.com/v1 -m gpt-4o -t GuardBench-EN
```

### Common Options

```bash
# With API key authentication
palace-run -u https://api.example.com/v1 -k your-api-key -m gpt-4o -t GuardBench-EN

# Limit number of tasks (useful for testing)
palace-run -u https://api.example.com/v1 -m gpt-4o -t GuardBench-EN -l 10

# Specify output directory
palace-run -u https://api.example.com/v1 -m gpt-4o -t GuardBench-EN --output-folder ./my-results

# Use MCP endpoint instead of OpenAI-compatible
palace-run -u http://localhost:8080/mcp/ -m my-agent -t GuardBench-EN --endpoint-type mcp
```

### All Options

| Option | Description | Default |
|--------|-------------|---------|
| `-u`, `--url` | API endpoint URL | Required |
| `-m`, `--name` | Model name to evaluate | Required |
| `-t`, `--tasklist` | Name of the tasklist to run | Required |
| `-k`, `--token` | API authentication token | None |
| `-l`, `--limit` | Maximum number of tasks to run | All tasks |
| `--output-folder` | Output directory for results | `~/.cache/palace/results/` |
| `--run-name` | Name for this evaluation run | Auto-generated |
| `--runs-per-configuration` | Number of runs to perform | 1 |
| `--endpoint-type` | `openai` or `mcp` | `openai` |

**Best for**: Scripted evaluations, CI/CD pipelines, batch processing.

## Method 3: Programmatic API

For integration into Python scripts and applications, use the `evaluate` function.

### Basic Usage

```python
from palace import evaluate

evaluate(
    run_name="my-evaluation",
    output_folder="./my-results",
    url="https://api.example.com/v1",
    token="your-api-key",
    name="gpt-4o",
    tasklist="GuardBench-EN"
)
```

### With Options

```python
from palace import evaluate

evaluate(
    run_name="guardench-test",
    output_folder="./my-results",
    url="https://api.example.com/v1",
    token="your-api-key",
    name="gpt-4o",
    tasklist="GuardBench-EN",
    limit=10,
    runs_per_configuration=3
)
```

### Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `run_name` | str | Name for this evaluation run | Required |
| `output_folder` | str | Output directory | Required |
| `url` | str | API endpoint URL | Required |
| `token` | str | API authentication token | None |
| `name` | str | Model name | Required |
| `tasklist` | str | Name of the tasklist | Required |
| `limit` | int | Maximum tasks to run | None (all) |
| `runs_per_configuration` | int | Number of runs | 1 |
| `endpoint_type` | str | `"openai"` or `"mcp"` | `"openai"` |

### Return Value

The `evaluate` function returns `None`. Results are written to the output folder as JSONL files.

**Best for**: Custom pipelines, integration with other tools, programmatic analysis.

## Batch Evaluations

### Running Multiple Tasklists

**CLI approach**:
```bash
for tasklist in GuardBench-EN Sycophancy-Binary DocRetrieval-ai; do
    palace-run -u https://api.example.com/v1 -m gpt-4o -t $tasklist --output-folder ./batch-results
done
```

**Python approach**:
```python
from palace import evaluate
import json

tasklists = ["GuardBench-EN", "Sycophancy-Binary", "DocRetrieval-ai"]

for tasklist in tasklists:
    evaluate(
        run_name=f"batch-{tasklist}",
        output_folder="./batch-results",
        url="https://api.example.com/v1",
        token="your-api-key",
        name="gpt-4o",
        tasklist=tasklist
    )
    print(f"Completed: {tasklist}")
```

### Comparing Models

```python
from palace import evaluate

models = [
    ("gpt-4o", "https://api.openai.com/v1", "key1"),
    ("claude-3", "https://api.anthropic.com/v1", "key2"),
]

for model_name, url, token in models:
    evaluate(
        run_name=f"comparison-{model_name}",
        output_folder=f"./results/{model_name}",
        url=url,
        token=token,
        name=model_name,
        tasklist="GuardBench-EN"
    )
    print(f"Completed: {model_name}")
```

## Understanding Output

### Results File

Results are saved as JSONL (one JSON object per evaluation run):

```bash
cat ~/.cache/palace/results/eval.jsonl | python -m json.tool
```

### Result Structure

Each evaluation produces a JSON object:

```json
{
    "agent": "gpt-4o",
    "model": "Unknown remote model",
    "paradigm": "Unknown remote paradigm",
    "environment": "Unknown Remote Environment",
    "tasklist": "GuardBench-EN",
    "accuracy": 0.85,
    "metrics": {
        "task_count": 20,
        "correct_count": 17,
        "total_time": 120.5
    },
    "detailed_report": {
        "GuardBench-EN_0": {
            "objective": "The prompt that was evaluated",
            "expected": "The expected output",
            "actual": "What the model produced",
            "is_correct": true,
            "reasoning": "Explanation of the verification result",
            "elapsed_time": 1.2
        }
    }
}
```

### Analyzing Results

```python
import json

# Load results
with open("results/eval.jsonl") as f:
    results = [json.loads(line) for line in f]

for run in results:
    print(f"Tasklist: {run['tasklist']}")
    print(f"Accuracy: {run['accuracy']:.1%}")
    
    # Find failures
    failures = [
        (task_id, data) 
        for task_id, data in run['detailed_report'].items() 
        if not data['is_correct']
    ]
    
    print(f"Failures: {len(failures)}")
    for task_id, data in failures[:3]:
        print(f"  {task_id}: {data['reasoning'][:100]}...")
```

## Environment Variables

Configure defaults via environment variables:

```bash
# API configuration
export OPENAI_LIKE_API_BASE_URL=https://api.example.com/v1
export OPENAI_LIKE_API_KEY=your-api-key

# Optional: judge model
export JUDGE_MODEL=gpt-4o
```

These are used by `palace-cli` for default values. The `palace-run` command requires explicit `-u` and `-m` arguments.

## Troubleshooting

### "Tasklist not found"

Ensure the tasklist is downloaded:

```bash
palace-download -t GuardBench-EN
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

- Use `-l` to reduce concurrent requests
- Add delays between evaluations in batch scripts
- Consider using a higher-tier API plan

### Out of Memory

For large tasklists:

- Use `-l` to process in batches
- Ensure sufficient disk space for results

---

## Related Pages

- [Quick Start](../getting-started/quickstart.md) — Run your first evaluation
- [Debug Evaluations](debug-evaluations.md) — Troubleshooting guide
- [CLI Reference](../reference/cli.md) — Complete command documentation
