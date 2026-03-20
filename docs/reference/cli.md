# CLI Reference

Complete reference for PALACE command-line tools.

## Commands Overview

| Command | Description |
|---------|-------------|
| `palace-cli` | Interactive menu-driven interface |
| `palace-run` | Run evaluations from command line |
| `palace-download` | Download tasklists from HuggingFace |

## palace-cli

Interactive CLI for exploring and running evaluations.

### Usage

```bash
palace-cli
```

### Features

- Browse available tasklists
- Configure evaluation parameters
- Run evaluations interactively
- View results

### Navigation

- Use arrow keys to navigate menus
- Press Enter to select
- Press `q` to quit

## palace-run

Run evaluations directly from the command line.

### Usage

```bash
palace-run --tasklist <name> [options]
```

### Required Arguments

| Argument | Description |
|----------|-------------|
| `--tasklist` | Name of the tasklist to evaluate |

### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--limit` | All tasks | Maximum number of tasks to run |
| `--output` | `~/.cache/palace/results/` | Output directory |
| `--model-url` | From env | API endpoint URL |
| `--model-token` | From env | API authentication token |
| `--model` | From env | Model name to use |
| `--verbose` | False | Enable detailed logging |

### Examples

```bash
# Basic evaluation
palace-run --tasklist GuardBench-EN

# Limit to 10 tasks
palace-run --tasklist GuardBench-EN --limit 10

# Custom output directory
palace-run --tasklist GuardBench-EN --output ./my-results

# Specify model endpoint
palace-run --tasklist GuardBench-EN \
    --model-url https://api.example.com/v1 \
    --model-token your-api-key \
    --model gpt-4o

# Verbose output
palace-run --tasklist GuardBench-EN --verbose
```

### Environment Variables

When not specified via arguments, these environment variables are used:

| Variable | Description |
|----------|-------------|
| `OPENAI_LIKE_API_BASE_URL` | API endpoint URL |
| `OPENAI_LIKE_API_KEY` | API authentication token |
| `JUDGE_API_BASE_URL` | Judge API endpoint (optional) |
| `JUDGE_API_KEY` | Judge API token (optional) |
| `JUDGE_MODEL` | Judge model name (optional) |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (invalid arguments, API failure, etc.) |

## palace-download

Download tasklists from HuggingFace.

### Usage

```bash
palace-download [options]
```

### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--tasklist` | All | Specific tasklist to download |

### Examples

```bash
# Download all available tasklists
palace-download

# Download specific tasklist
palace-download --tasklist GuardBench-EN

# Download by full HuggingFace ID
palace-download --tasklist jrc-ai/GuardBench-EN
```

### Download Location

Tasklists are downloaded to:

| Platform | Location |
|----------|----------|
| Linux | `~/.cache/palace/tasklists/` |
| macOS | `~/Library/Caches/palace/tasklists/` |
| Windows | `C:\Users\<user>\AppData\Local\palace\Cache\tasklists\` |

### Available Tasklists

Run `palace-download` without arguments to see available tasklists.

## Common Workflows

### Quick Test

```bash
# Download and run with limit
palace-download --tasklist GuardBench-EN
palace-run --tasklist GuardBench-EN --limit 5
```

### Full Evaluation

```bash
palace-run --tasklist GuardBench-EN --output ./results/guardench
```

### Batch Evaluation

```bash
for tasklist in GuardBench-EN Sycophancy-Binary DocRetrieval-ai; do
    palace-run --tasklist $tasklist --output ./batch-results
done
```

### Compare Models

```bash
# Model A
OPENAI_LIKE_API_BASE_URL=https://api-a.example.com/v1 \
palace-run --tasklist GuardBench-EN --output ./results/model-a

# Model B
OPENAI_LIKE_API_BASE_URL=https://api-b.example.com/v1 \
palace-run --tasklist GuardBench-EN --output ./results/model-b
```

## Troubleshooting

### "Tasklist not found"

```bash
# Check available tasklists
ls ~/.cache/palace/tasklists/

# Download if missing
palace-download --tasklist <name>
```

### "API connection error"

```bash
# Verify environment variables
echo $OPENAI_LIKE_API_BASE_URL
echo $OPENAI_LIKE_API_KEY

# Test connectivity
curl -H "Authorization: Bearer $OPENAI_LIKE_API_KEY" \
     "$OPENAI_LIKE_API_BASE_URL/models"
```

### "Invalid JSON"

```bash
# Validate tasklist files
python -c "import json; json.load(open('info.json')); print('Valid')"
python -c "import json; json.load(open('tasks.json')); print('Valid')"
```

---

## Related Pages

- [Run Evaluations](../howto/run-evaluations.md) — Detailed usage guide
- [Installation](../getting-started/installation.md) — Setup and configuration
- [Debug Evaluations](../howto/debug-evaluations.md) — Troubleshooting
