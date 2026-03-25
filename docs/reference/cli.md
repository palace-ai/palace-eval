# CLI Reference

Complete reference for PALACE command-line tools.

## Commands Overview

| Command | Description |
|---------|-------------|
| `palace-cli` | Interactive menu-driven interface |
| `palace-run` | Run evaluations from command line |
| `palace-download` | Download tasklists from HuggingFace |
| `palace-mcpstart` | Start the MCP SSE server |

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
palace-run -u <url> -m <model-name> -t <tasklist> [options]
```

### Required Arguments

| Argument | Description |
|----------|-------------|
| `-u`, `--url` | API endpoint URL (OpenAI-compatible) |
| `-m`, `--name` | Model name to evaluate |
| `-t`, `--tasklist` | Name of the tasklist to evaluate |

### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `-k`, `--token` | None | API authentication token |
| `-l`, `--limit` | All tasks | Maximum number of tasks to run |
| `--output-folder` | `~/.cache/palace/results/` | Output directory |
| `--run-name` | `eval` | Name for this evaluation run |
| `--runs-per-configuration` | 1 | Number of evaluation runs to perform |
| `--endpoint-type` | `openai` | Endpoint type: `openai` or `mcp` |

### Examples

```bash
# Basic evaluation
palace-run -u https://api.example.com/v1 -m gpt-4o -t GuardBench-EN

# With authentication
palace-run -u https://api.example.com/v1 -k your-api-key -m gpt-4o -t GuardBench-EN

# Limit to 10 tasks
palace-run -u https://api.example.com/v1 -m gpt-4o -t GuardBench-EN -l 10

# Custom output directory
palace-run -u https://api.example.com/v1 -m gpt-4o -t GuardBench-EN --output-folder ./my-results

# MCP endpoint
palace-run -u http://localhost:8080/mcp/ -m my-agent -t GuardBench-EN --endpoint-type mcp
```

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
| `-t`, `--tasklists` | All | Specific tasklist(s) to download |
| `--skip-existing` | False | Skip tasklists that already exist locally |

### Examples

```bash
# Download all available tasklists
palace-download

# Download specific tasklist
palace-download -t GuardBench-EN

# Download multiple tasklists
palace-download -t GuardBench-EN Sycophancy-Binary

# Skip already downloaded
palace-download --skip-existing
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

## palace-mcpstart

Start a PALACE MCP (Model Context Protocol) SSE server, allowing external tools to run evaluations via MCP.

### Usage

```bash
palace-mcpstart [--host HOST] [--port PORT]
```

### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--host` | `0.0.0.0` | Host to bind the server to |
| `--port` | `8080` | Port to listen on |

## Environment Variables

PALACE uses the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_LIKE_API_BASE_URL` | API endpoint for the judge model | Required for QA and Report Generation |
| `OPENAI_LIKE_API_KEY` | API key for the judge endpoint | Required for QA and Report Generation |
| `JUDGE_MODEL` | Model used for LLM-based judging (QA and Report Generation) | `minimax-m2` |
| `ENABLE_CITATION_VERIFIER` | Enable the citation verifier analyzer (`true`/`false`) | `false` |

## Common Workflows

### Quick Test

```bash
# Download and run with limit
palace-download -t GuardBench-EN
palace-run -u https://api.example.com/v1 -m gpt-4o -t GuardBench-EN -l 5
```

### Full Evaluation

```bash
palace-run -u https://api.example.com/v1 -k $API_KEY -m gpt-4o -t GuardBench-EN --output-folder ./results/guardench
```

### Batch Evaluation

```bash
for tasklist in GuardBench-EN Sycophancy-Binary DocRetrieval-ai; do
    palace-run -u https://api.example.com/v1 -m gpt-4o -t $tasklist --output-folder ./batch-results
done
```

### Compare Models

```bash
# Model A
palace-run -u https://api-a.example.com/v1 -m model-a -t GuardBench-EN --output-folder ./results/model-a

# Model B
palace-run -u https://api-b.example.com/v1 -m model-b -t GuardBench-EN --output-folder ./results/model-b
```

## Troubleshooting

### "Tasklist not found"

```bash
# Check available tasklists
ls ~/.cache/palace/tasklists/

# Download if missing
palace-download -t <name>
```

### "API connection error"

```bash
# Test connectivity
curl -H "Authorization: Bearer $API_KEY" \
     "https://api.example.com/v1/models"
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
