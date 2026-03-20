# Installation

This guide walks you through installing PALACE and configuring your environment. By the end, you'll have a working installation ready to run evaluations.

## Requirements

PALACE requires:

- **Python 3.13 or higher** — PALACE uses modern Python features
- **pip** — Python's package installer
- **An OpenAI-compatible API endpoint** — For running evaluations and LLM judges

## Installation

### Step 1: Clone the Repository

```bash
git clone <repository-url> palace
cd palace
```

### Step 2: Create a Virtual Environment

We recommend using a dedicated environment to avoid dependency conflicts.

=== "conda"

    ```bash
    conda create -n palace python=3.13
    conda activate palace
    ```

=== "venv"

    ```bash
    python3.13 -m venv .venv
    source .venv/bin/activate  # Linux/macOS
    # or
    .venv\Scripts\activate     # Windows
    ```

### Step 3: Install PALACE

```bash
pip install -e .
```

The `-e` flag installs in "editable" mode, useful if you plan to modify PALACE or contribute changes.

### Step 4: Verify Installation

```bash
palace-cli
```

You should see the interactive CLI menu. Press `q` to exit.

## Configuration

PALACE needs API credentials to run evaluations. The model being evaluated and the LLM judge both use OpenAI-compatible APIs.

### Environment Variables

Create a `.env` file in your working directory or set these environment variables:

```bash
# Required: API endpoint for the model being evaluated
OPENAI_LIKE_API_BASE_URL=https://api.example.com/v1
OPENAI_LIKE_API_KEY=your-api-key

# Optional: Model to use for judging (defaults to minimax-m2)
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
| `OPENAI_LIKE_API_BASE_URL` | Yes | Base URL for the OpenAI-compatible API |
| `OPENAI_LIKE_API_KEY` | Yes | API key for authentication |
| `JUDGE_MODEL` | No | Model to use for LLM judging in QA and Report Generation tasks (default: minimax-m2) |

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

---

## Next Steps

- [Quick Start](quickstart.md) — Run your first evaluation in 5 minutes
- [Your First Benchmark](first-benchmark.md) — Create a custom tasklist from scratch
