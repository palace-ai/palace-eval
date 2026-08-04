# Installation

This guide walks you through installing PALACE and configuring your environment. By the end, you'll have a working installation ready to run evaluations.

## Requirements

PALACE requires:

- **Python 3.13 or higher** — PALACE uses modern Python features
- **pip** — Python's package installer
- **An OpenAI-compatible API endpoint** — For running evaluations and LLM judges

## Installation

### Quick Install (Recommended)

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

```bash
palace-cli
```

You should see the interactive CLI menu. Press `q` to exit.

## Configuration

PALACE needs API credentials to run evaluations. The model being evaluated receives its endpoint via the `-u` flag (or `url` parameter). The LLM judge — used for QA and Criteria Evaluation verification — reads its endpoint from environment variables.

### Environment Variables

Create a `.env` file in your working directory or set these environment variables:

```bash
# Required for QA and Criteria Evaluation: API endpoint for the LLM judge
OPENAI_LIKE_API_BASE_URL=https://api.example.com/v1
OPENAI_LIKE_API_KEY=your-api-key

# Required: Model to use for judging
JUDGE_MODEL=gpt-4o
```

If you have a `.env.example` file in the repository:

```bash
cp .env.example .env
# Edit .env with your credentials
```

### Configuration Options

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_LIKE_API_BASE_URL` | For QA / Criteria Evaluation | Base URL for the LLM judge API endpoint |
| `OPENAI_LIKE_API_KEY` | For QA / Criteria Evaluation | API key for the judge endpoint |
| `JUDGE_MODEL` | For QA / Criteria Evaluation | Model to use for LLM judging |

## Download Tasklists

PALACE benchmarks are distributed as "tasklists" hosted on HuggingFace. Download the official collection:

```bash
palace-download
```

This downloads all available tasklists to your user data directory:

| Platform | Location |
|----------|----------|
| Linux | `~/.cache/palace/tasklists/` |
| macOS | `~/Library/Caches/palace/tasklists/` |
| Windows | `C:\Users\<user>\AppData\Local\palace\Cache\tasklists\` |

You can also download specific tasklists:

```bash
palace-download -t GuardBench-EN
```

## Platform-Specific Notes

### Linux

No special requirements. Ensure Python 3.13+ is installed:

```bash
python3 --version  # Should show 3.13.x or higher
```

If your distribution doesn't have Python 3.13, consider using [pyenv](https://github.com/pyenv/pyenv) or conda.

### macOS

Install Python 3.13 via Homebrew if needed:

```bash
brew install python@3.13
```

Or use conda/pyenv for version management.

### Windows

1. Download Python 3.13 from [python.org](https://www.python.org/downloads/)
2. During installation, check "Add Python to PATH"
3. Use PowerShell or Command Prompt for the installation commands

For the virtual environment activation:
```powershell
.venv\Scripts\Activate.ps1  # PowerShell
# or
.venv\Scripts\activate.bat  # Command Prompt
```

## Troubleshooting

### "Python 3.13 not found"

PALACE requires Python 3.13+. Check your version:

```bash
python3 --version
```

If you have multiple Python versions, specify the correct one:

```bash
python3.13 -m venv .venv
```

### "Module not found" errors

Ensure you're in the activated virtual environment:

```bash
which python  # Should point to your venv
# or on Windows:
where python
```

If not, activate the environment again.

### API connection errors

1. Verify your API URL is correct (should end with `/v1` for OpenAI-compatible APIs)
2. Check your API key is valid
3. Ensure the endpoint is reachable from your network

Test with curl:
```bash
curl -H "Authorization: Bearer $OPENAI_LIKE_API_KEY" \
     "$OPENAI_LIKE_API_BASE_URL/models"
```

### Download failures

If `palace-download` fails:

1. Check your internet connection
2. Verify HuggingFace is accessible
3. Try downloading a specific tasklist: `palace-download -t GuardBench-EN`

## Agentic Evaluation (Optional)

Some benchmarks (e.g., Tau2-bench) require agentic evaluation — the model runs in a sandboxed Docker environment with access to tools like bash, file I/O, and web search. This is powered by [Vivarium](https://code.europa.eu/palace/vivarium), a managed agent runtime.

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

Vivarium starts automatically when you run an agentic tasklist — no manual startup required.

---

## Next Steps

- [Quick Start](quickstart.md) — Run your first evaluation in 5 minutes
- [Your First Benchmark](first-benchmark.md) — Create a custom tasklist from scratch
