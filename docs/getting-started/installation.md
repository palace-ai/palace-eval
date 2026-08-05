
This guide walks you through installing PALACE and configuring your environment. By the end, you'll have a working installation ready to run evaluations.

## Requirements

PALACE requires:

- **Python 3.13 or higher** — PALACE uses modern Python features
- **pip or uv** — Python package installer
- **An OpenAI-compatible API endpoint** — For running evaluations and LLM judges

## Installation

### Quick Install (Recommended)

Using uv (recommended for CLI tools):

```bash
uv tool install palace-eval
```

Or with pip:

```bash
pip install palace-eval
```

### Development Install

If you want to modify PALACE or contribute changes:

```bash
git clone https://code.europa.eu/palace/palace-eval.git
cd palace-eval
pip install -e .
```

### Verify Installation

```bash
palace version
```

You should see the version number. Run `palace` to see available commands.

## Configuration

PALACE needs API credentials to run evaluations. Configure them with the CLI:

```bash
palace config set url https://api.openai.com/v1
palace config set key sk-your-api-key
palace config set judge_model gpt-4o
```

Check your configuration:

```bash
palace config
```

### Configuration Options

| Setting | Required | Description |
|---------|----------|-------------|
| `url` | Yes | API endpoint URL (OpenAI-compatible) |
| `key` | Yes | API key for the endpoint |
| `judge_model` | Yes | Model to use for answer verification |
| `concurrency` | No | Number of parallel tasks (default: 25) |
| `huggingface_token` | No | For gated datasets (GAIA, GPQA Diamond) |
| `github_token` | No | For higher GitHub API rate limits |

### Alternative: Environment Variables

You can also use environment variables (useful for CI/Docker):

```bash
export OPENAI_LIKE_API_BASE_URL=https://api.openai.com/v1
export OPENAI_LIKE_API_KEY=sk-your-api-key
export JUDGE_MODEL=gpt-4o
```

Environment variables take priority over the config file.

## Download Benchmarks

List available benchmarks:

```bash
palace list
```

Download a specific benchmark:

```bash
palace download MMLU
palace download "GPQA Diamond"
```

Or download all benchmarks:

```bash
palace download --all
```

Benchmarks are stored in your user cache directory:

| Platform | Location |
|----------|----------|
| Linux | `~/.cache/palace/tasklists/` |
| macOS | `~/Library/Caches/palace/tasklists/` |
| Windows | `C:\Users\<user>\AppData\Local\palace\Cache\tasklists\` |

## Platform-Specific Notes

### Linux

No special requirements. Ensure Python 3.13+ is installed:

```bash
python3 --version  # Should show 3.13.x or higher
```

If your distribution doesn't have Python 3.13, consider using [pyenv](https://github.com/pyenv/pyenv) or [uv](https://docs.astral.sh/uv/).

### macOS

Install Python 3.13 via Homebrew if needed:

```bash
brew install python@3.13
```

Or use uv/conda/pyenv for version management.

### Windows

1. Download Python 3.13 from [python.org](https://www.python.org/downloads/)
2. During installation, check "Add Python to PATH"
3. Use PowerShell or Command Prompt for the installation commands

## Troubleshooting

### "Python 3.13 not found"

PALACE requires Python 3.13+. Check your version:

```bash
python3 --version
```

If using uv, it will automatically fetch the correct Python version:

```bash
uv tool install palace-eval
```

### API connection errors

1. Verify your API URL is correct (should end with `/v1` for OpenAI-compatible APIs)
2. Check your API key is valid
3. Ensure the endpoint is reachable from your network

Test with curl:

```bash
curl -H "Authorization: Bearer $(palace config get key)" \
     "$(palace config get url)/models"
```

### Download failures

If `palace download` fails:

1. Check your internet connection
2. Verify HuggingFace is accessible
3. For gated datasets, set your HuggingFace token:
   ```bash
   palace config set huggingface_token hf_your_token
   ```

## Agentic Evaluation (Optional)

Some benchmarks (GAIA, SWE-bench, etc.) require agentic evaluation — the model runs in a sandboxed Docker environment with access to tools like bash, file I/O, and web search. This is powered by [Vivarium](https://code.europa.eu/palace/vivarium), a managed agent runtime.

### Additional Requirements

- **Docker 24+** — installed and running
- **Vivarium SDK** — `pip install vivarium-ai`

### Install Vivarium

```bash
pip install vivarium-ai
```

### Verify

```bash
vivarium start
vivarium status
vivarium stop
```

Vivarium starts automatically when you run an agentic benchmark — no manual startup required.

---

## Next Steps

- [Quickstart](quickstart.md) — Run your first evaluation
- [Your First Benchmark](first-benchmark.md) — Create a custom benchmark
