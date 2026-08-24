# How to Run Evaluations

This guide covers all the ways to run PALACE evaluations: command-line interface and programmatic API.

## Prerequisites

- PALACE installed ([Installation Guide](../getting-started/installation.md))
- API credentials configured (`palace config set url/key/judge_model`)
- At least one benchmark downloaded (`palace download BENCHMARK`)

## Method 1: Command-Line Interface

### Basic Usage

```bash
palace run MMLU -m gpt-4o
```

### Common Options

```bash
# With specific endpoint (overrides config)
palace run MMLU -m gpt-4o -u https://api.example.com/v1 -k your-api-key

# Limit number of tasks (useful for testing)
palace run MMLU -m gpt-4o -l 10

# Specify output directory
palace run MMLU -m gpt-4o -o ./my-results

# Agentic evaluation (requires Docker + Vivarium)
palace run SWE-bench -m o3-mini --agentic
```

### All Options

| Option | Description | Default |
|--------|-------------|---------|
| `-m`, `--model` | Model name to evaluate | Required |
| `-u`, `--url` | API endpoint URL | From config |
| `-k`, `--token` | API authentication token | From config |
| `-l`, `--limit` | Maximum number of tasks to run | All tasks |
| `-o`, `--output` | Output directory for results | `~/.cache/palace/results/` |
| `--name` | Name for this evaluation run | `eval` |
| `--runs` | Number of runs to perform | 1 |
| `--agentic` | Run in sandboxed environment via Vivarium | Auto-detect |
| `-y`, `--yes` | Skip confirmation prompts | False |

**Best for**: Scripted evaluations, CI/CD pipelines, batch processing.

## Method 2: Programmatic API

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
    tasklist="GuardBench-EN",
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
    runs_per_configuration=3,
    report_detail="full",  # "none", "default", or "full"
)
```

### With I/O Adapter

For specialized models (e.g., guardrail classifiers) that need custom input/output formatting:

```python
from palace import evaluate

evaluate(
    run_name="llamaguard-test",
    output_folder="./my-results",
    url="http://localhost:8000/v1",
    name="llamaguard-7b",
    tasklist="GuardBench-EN",
    io_adapter={
        "input": {"template": "{objective}"},
        "output": {
            "pattern": "(?P<result>safe|unsafe)",
            "template": "<Unsafe>{result}</Unsafe>",
            "mapping": {"result": {"safe": "No", "unsafe": "Yes"}},
        },
    },
)
```

See [Model Adapters](model-adapters.md) for the full adapter reference.

### Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `run_name` | str | Name for this evaluation run | Required |
| `output_folder` | str | Output directory | Required |
| `url` | str | API endpoint URL | Required |
| `token` | str | API authentication token | None |
| `name` | str | Model name | Required |
| `tasklist` | str | Name of the benchmark | Required |
| `limit` | int | Maximum tasks to run | None (all) |
| `runs_per_configuration` | int | Number of runs | 1 |
| `endpoint_type` | str | `"auto"`, `"openai"`, `"anthropic"`, `"azure"`, or `"mcp"` | `"auto"` |
| `io_adapter` | dict | I/O adapter config (see [Model Adapters](model-adapters.md)) | None |
| `on_task_complete` | callable | Callback invoked after each task with `(current, total)` for progress tracking | None |

!!! tip "Anthropic Models"
    For direct Anthropic API access, set `endpoint_type="anthropic"` and use `url="https://api.anthropic.com"` with your Anthropic API key.

**Best for**: Python scripts, notebooks, custom tooling, integration tests.

## Choosing a Method

| Scenario | Recommended Method |
|----------|-------------------|
| Quick one-off evaluation | CLI: `palace run` |
| CI/CD pipeline | CLI with flags |
| Integration into Python app | Programmatic API |
| Batch processing multiple models | Programmatic API with loop |
| Custom progress reporting | Programmatic API with `on_task_complete` |

## Next Steps

- [Understanding Results](../concepts/evaluation-pipeline.md#output-format) — How to interpret evaluation output
- [Model Adapters](model-adapters.md) — Configure I/O transformations for specialized models
- [Creating Benchmarks](../getting-started/first-benchmark.md) — Build your own benchmark
