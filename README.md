# PALACE

![img](https://img.shields.io/badge/python-3.13+-orange)

A framework to evaluate the capabilities of LLMs across diverse benchmarks.

<img src="assets/readme_images/logo.png" width="300" alt="logo.png">

## Description

**PALACE** is a **P**latform for **A**utomated **L**LMs **A**gentic **C**apabilities **E**valuation.
It can quantitatively assess the performance of AI models and agents across several different benchmarks covering reasoning, knowledge, safety, multilingual, multimodal, and instruction-following capabilities.

The framework supports evaluation of any model accessible via an OpenAI-compatible API endpoint. Benchmark tasklists can be easily downloaded from HuggingFace or created custom.

The output of an evaluation run is a JSONL file containing per-task results, metrics, and judge assessments. This information can be used to build user-friendly results visualizations.

## Installation

**PALACE** is provided as a Python package. It requires Python 3.13+.

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone the project:**
   ```bash
   git clone https://gitlab.jrc.ec.europa.eu/jrc-projects/jrc-gpt/evaluation/palace-lib.git
   cd palace-lib
   ```

3. **Install dependencies** (uv will automatically create a virtual environment):
   ```bash
   uv sync
   ```

4. **Configure environment variables:**

   4.1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

   4.2. Open `.env` and set the **required** variables (at minimum `OPENAI_LIKE_API_BASE_URL` and `OPENAI_LIKE_API_KEY`). The file is organized into sections — see the comments for guidance.

That's it! You are ready to use PALACE.

### Agentic evaluation (optional)

To run agentic benchmarks (tasks requiring sandboxed tool execution), you also need:

- Docker 24+ (running)
- The vivarium SDK:

```bash
git clone https://gitlab.jrc.ec.europa.eu/jrc-projects/jrc-gpt/research/vivarium.git
uv pip install -e vivarium/
```

Vivarium (the agent runtime) will start automatically when you select an agentic tasklist — no manual setup required.

## Quick Start

Here's a complete example to evaluate a model on the SimpleQA benchmark:

```bash
# 1. Download the SimpleQA tasklist (no HuggingFace token required for public datasets)
uv run -- palace-download -t SimpleQA

# 2. Run the evaluation against an OpenAI-compatible endpoint
uv run -- palace-run -u https://api.openai.com/v1 -k $OPENAI_LIKE_API_KEY -m gpt-4o -t SimpleQA -l 20
```

This will evaluate `gpt-4o` on 20 tasks from SimpleQA and save results to `~/.cache/palace/results/`.

## Downloading Tasklists

Before running evaluations, you need to download the benchmark tasklists using `palace-download`.

### Download all tasklists

To download all available tasklists (requires a HuggingFace token for gated datasets):

```bash
uv run -- palace-download
```

### Download specific tasklists

To download only specific tasklists:

```bash
uv run -- palace-download -t SimpleQA HotpotQA
```

Most datasets can be downloaded without a HuggingFace token. Gated datasets (GAIA, GPQA Diamond, SuperGPQA) require one.

### Skip existing tasklists

To skip tasklists that are already downloaded:

```bash
uv run -- palace-download --skip-existing
```

### HuggingFace token

For gated datasets, set the `HUGGINGFACE_TOKEN` environment variable in your `.env` file. You can get a token from [HuggingFace Settings](https://huggingface.co/settings/tokens).

Tasklists are downloaded to the user data directory:
- Linux: `~/.cache/palace/tasklists/`
- macOS: `~/Library/Caches/palace/tasklists/`
- Windows: `C:\Users\<user>\AppData\Local\palace\Cache\tasklists\`

## Usage

There are **3** supported ways to use PALACE: (1) via the **interactive CLI**, (2) via the **direct command**, or (3) **programmatically**.

### CLI

The easiest way to start using PALACE is the interactive CLI:

```bash
uv run -- palace-cli
```

This opens an interactive menu where you configure your evaluation run step by step:
<img src="assets/readme_images/cli.png" width="600" alt="cli.png">

Use the arrow keys to navigate, Space to select options, and Enter to confirm. The CLI will guide you through selecting:

- The API endpoint and model to evaluate,
- The benchmark tasklists to use,
- Number of tasks per tasklist (useful for quick tests),
- Number of runs (to reduce variance),
- The evaluation run name.

After configuration, the evaluation starts:
<img src="assets/readme_images/cli2.png" width="600" alt="cli2.png">

Results are saved to `~/.cache/palace/results/<run_name>.jsonl`.

### Direct Command

For scripted or batch evaluations, use `palace-run`:

```bash
uv run -- palace-run --help
```

The `-k/--token` parameter can be omitted if `OPENAI_LIKE_API_KEY` is set in your `.env`.

**Example:**

```bash
uv run -- palace-run \
   --run-name=MyEval \
   -u https://api.mistral.ai/v1 \
   -k abc123def456 \
   -m mistral-medium-latest \
   -t SimpleQA \
   -l 50
```

**Full options:**

| Flag | Description |
|------|-------------|
| `-u, --url` | API endpoint URL (required) |
| `-k, --token` | API key (or set `OPENAI_LIKE_API_KEY`) |
| `-m, --name` | Model name (omit to list available models) |
| `-t, --tasklist` | Tasklist(s) to evaluate on (repeatable: `-t T1 -t T2`) |
| `-l, --limit` | Max tasks per tasklist |
| `-c, --concurrency` | Parallel tasks (default: `PALACE_CONCURRENCY` env, or 25) |
| `--endpoint-type` | `openai` (default), `azure`, or `mcp` |
| `--report-detail` | Output detail: `none`, `default`, or `full` |
| `--agentic` | Force agentic execution via Vivarium |
| `--param KEY=VALUE` | Extra model params (repeatable, e.g., `--param temperature=0.5`) |
| `--run-name` | Name for the evaluation run |
| `--output-folder` | Output path (default: `~/.cache/palace/results/`) |
| `--runs-per-configuration` | Number of repeated runs (default: 1) |

### Programmatic API

Integrate PALACE into your Python code:

```python
from palace import evaluate

evaluate(
   run_name="My Evaluation",         # evaluation run name
   url="https://api.mistral.ai/v1",  # your API URL
   token="abc123def456",             # your API token
   name="mistral-medium-latest",     # model name
   tasklist="SimpleQA",              # PALACE tasklist to use
   limit=100,                        # optional: max tasks per tasklist
   runs_per_configuration=1,         # optional: repeated runs
   concurrency=25,                   # optional: parallel tasks
   endpoint_type="openai",           # optional: "openai", "azure", or "mcp"
   report_detail="default",          # optional: "none", "default", or "full"
)
```

Additional optional parameters:
- `output_folder` — where to save results (default: `~/.cache/palace/results/`)
- `io_adapter` — I/O adapter config dict for specialized models
- `model_extra_params` — extra inference parameters (e.g., `{"temperature": 0.5}`)
- `agentic` — force agentic execution via Vivarium
- `vivarium_url` — custom Vivarium service URL

Results are saved to `<output_folder>/<run_name>.jsonl`.

## Tasklists

Benchmark datasets in PALACE have a standard format.
A dataset is internally called _tasklist_, and it mainly consists of a JSON file `tasks.json` containing the actual _tasks_.
Additionally, a tasklist may have a `task_files` folder containing files referenced in the tasks.
The directory structure is the following:

```
<tasklist_name>
├─ task_files/
│  ├─ file_1
│  ├─ ...
│  └─ file_n
├─ tasks.json
└─ info.json
```

A task is a JSON object containing the following fields (fields with an asterisk are mandatory):

- **(\*) id**: Unique identifier for the task.
- **(\*) objective**: The main goal or prompt for the task.
- **expected**: The expected answer or outcome.
- **references**: Supporting references or information.
- **difficulty**: Difficulty level of the task.
- **document**: Related document.
- **attachment**: Filename or path to an attachment (text, image, audio).
- **custom_verificator**: Custom verification logic or script.
- Any task-type-specific fields as defined in `task_type_fields` in `info.json`.

The `info.json` file contains metadata: `name`, `id`, `config`, `split`, `category`, `task_type`, `task_type_fields`, `input_modalities`, `output_modalities`.

### Supported tasklists

PALACE includes 27 vetted tasklists covering multiple evaluation categories:

**General Knowledge & Reasoning**
- **SimpleQA**: straightforward factual questions *(basicv8vc/SimpleQA)*
- **SimpleQA-Verified**: curated subset with verified answers *(google/simpleqa-verified)*
- **HotpotQA**: multi-hop question answering *(hotpotqa/hotpot_qa)*
- **Humanity's Last Exam**: graduate-level questions across diverse fields *(cais/hle)*
- **SuperGPQA**: graduate-level professional QA *(m-a-p/SuperGPQA)* 🔒
- **GPQA Diamond**: expert-level science questions *(Idavidrein/gpqa)* 🔒
- **MUSR**: multi-step reasoning *(edinburgh-dawg/labelchaos)*

**Academic & Math**
- **MMLU**: massive multitask language understanding *(cais/mmlu)*
- **MMLU-Pro**: harder MMLU variant with 10 choices *(TIGER-Lab/MMLU-Pro)*
- **MATH-500**: competition-level math problems *(HuggingFaceH4/MATH-500)*
- **AIME 2025**: American Invitational Mathematics Examination *(AI-MO/aimo-validation-aime)*
- **BBH**: Big Bench Hard — 27 challenging subtasks *(lukaemon/bbh)*
- **HellaSwag**: commonsense reasoning via sentence completion *(Rowan/hellaswag)*

**Multilingual**
- **MMMLU**: multilingual MMLU across 14 languages *(openai/MMMLU)*
- **MGSM**: multilingual grade-school math *(juletxara/mgsm)*
- **Belebele**: multilingual reading comprehension, 122 languages *(facebook/belebele)*

**Long Context**
- **BABILong-32k**: long-context reasoning over 32k tokens *(RMT-team/babilong)*
- **BABILong-128k**: long-context reasoning over 128k tokens *(RMT-team/babilong)*
- **BABILong**: unified long-context benchmark (4k–128k) *(RMT-team/babilong)*
- **LongBench v2**: diverse long-context tasks *(zai-org/LongBench-v2)*

**Multimodal**
- **VLSBench**: vision-language safety benchmark *(Foreshhh/vlsbench)*
- **MMMU**: multimodal understanding across disciplines *(MMMU/MMMU)*
- **MMMU Pro**: harder multimodal variant *(MMMU/MMMU_Pro)*

**Instruction Following**
- **IFEval**: instruction following with verifiable constraints *(google/IFEval)*

**Agentic** (require Vivarium)
- **GAIA**: real-world tasks requiring web access and tools *(gaia-benchmark/GAIA)* 🔒
- **AssistantBench**: real-world web-based tasks *(AssistantBench/AssistantBench)*

**Domain-Specific**
- **CURIE-protein**: protein sequence reconstruction *(nhop/curie)*

🔒 = Gated dataset (requires `HUGGINGFACE_TOKEN`)

### Adding a custom tasklist

To add a custom tasklist, create files in the user data directory (e.g., `~/.cache/palace/tasklists/` on Linux):

- `<tasklist_name>/tasks.json` — list of tasks in the format described above
- `<tasklist_name>/info.json` — tasklist metadata
- optionally, `<tasklist_name>/task_files/` — folder containing referenced files

Your custom tasklist will be automatically available for evaluation.

## FAQ

- **"I want to evaluate my model that is deployed on a private endpoint."**

   Clone PALACE, install it, set your endpoint URL and API key in `.env`, and run `palace-run` or `palace-cli` pointing to your endpoint.

- **"I want the online PALACE instance (Gradin) to evaluate my model."**

   Your model needs to be accessible via an OpenAI-compatible API endpoint. Contact the team and we'll configure Gradin to evaluate it.

- **"How do I save scores to Palace Vault?"**

   Run evaluations locally with PALACE. Scores can be imported into Vault via CSV or pushed directly from Gradin.

## Support

If you have any issues, you can open an issue on the [GitLab repository](https://gitlab.jrc.ec.europa.eu/jrc-projects/jrc-gpt/evaluation/palace-lib), or you can contact me at massimiliano.altieri@ec.europa.eu.
