# PALACE

[![License: EUPL-1.2](https://img.shields.io/badge/License-EUPL--1.2-blue.svg)](https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-orange.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/palace-eval.svg)](https://pypi.org/project/palace-eval/)
[![CI](https://github.com/palace-ai/palace-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/palace-ai/palace-eval/actions/workflows/ci.yml)

<img src="https://code.europa.eu/palace/palace-eval/-/raw/main/assets/readme_images/logo.png" width="280" alt="PALACE logo">

**PALACE** is an open benchmark format for LLM evaluation, with native support for agentic tasks.

Benchmarks should be portable. A PALACE benchmark is a self-contained folder with two JSON files: `info.json` (metadata and evaluation config) and `tasks.json` (the actual tasks). No framework lock-in, no Python decorators, no code to run. Just data that any tool can read.

`palace-eval` is the reference implementation.

## Quick start

**1. Install:**

```bash
uv tool install palace-eval   # recommended
# or: pip install palace-eval
```

**2. Configure your API:**

```bash
palace config set url https://api.openai.com/v1
palace config set key sk-your-api-key
palace config set judge_model gpt-4o
```

**3. Run your first evaluation:**

```bash
palace download SimpleQA
palace run SimpleQA -m gpt-4o -l 10
```

That's it. Results go to `~/.cache/palace/results/`.

Run `palace config` anytime to see your current settings.

## Why another benchmark format?

Most benchmarks today are tied to specific frameworks. LM-eval-harness tasks are Python code. Inspect-AI uses `@task` decorators. If you want to run a benchmark, you need their infrastructure.

PALACE takes a different approach:

- **Self-contained**: everything travels together (tasks, expected outputs, judge criteria, evaluation logic)
- **HuggingFace-distributed**: download with `palace download`, standard hosting and discovery  
- **Agentic-native**: tool-using agents are a first-class task type
- **Framework-agnostic**: palace-eval runs them, but so could anything else

We ship 27+ benchmarks covering reasoning, knowledge, safety, multilingual, multimodal, and agentic capabilities.

## The format

A PALACE benchmark is just two JSON files:

```
SimpleQA/
├── info.json      # what kind of benchmark, how to evaluate
└── tasks.json     # the actual tasks
```

**info.json** defines the benchmark:

```json
{
  "name": "SimpleQA",
  "id": "openai/SimpleQA", 
  "task_type": "QA",
  "category": "Knowledge"
}
```

**tasks.json** contains the tasks:

```json
[
  {"id": "q1", "objective": "What is the capital of France?", "expected": "Paris"},
  {"id": "q2", "objective": "Who wrote Romeo and Juliet?", "expected": "Shakespeare"}
]
```

The format supports five task types (QA, Classification, Criteria Evaluation, Instruction Following, and Agentic), each with its own verification logic. See the [full spec](https://palace.pages.code.europa.eu/palace-eval/reference/info-json/).

## Configuration

Palace stores settings in `~/.config/palace/config.yaml`. The quick start covers the essentials. 

For CI/Docker, use environment variables instead. Run `palace config env` to see the mapping.

## Included benchmarks

| Category | Benchmarks |
|----------|------------|
| Knowledge & Reasoning | SimpleQA, HotpotQA, Humanity's Last Exam, GPQA Diamond, MUSR |
| Academic & Math | MMLU, MMLU-Pro, MATH-500, AIME 2025, BBH, HellaSwag |
| Multilingual | MMMLU (14 languages), MGSM, Belebele (122 languages) |
| Long Context | BABILong (4k-128k), LongBench v2 |
| Multimodal | MMMU, MMMU Pro, VLSBench |
| Instruction Following | IFEval |
| Agentic | GAIA, AssistantBench |

```bash
palace list                    # see all available
palace download MMLU           # download one
palace download --all          # download everything
```

## Running evaluations

```bash
palace run MMLU -m gpt-4o
palace run MMLU -m gpt-4o -l 50           # limit to 50 tasks
palace run "GPQA Diamond" -m claude-sonnet
palace run SWE-bench -m o3-mini --agentic # agentic benchmark
```

**Python API** (for integration):

```python
from palace import evaluate

evaluate(
    run_name="my-eval",
    url="https://api.openai.com/v1",
    token="sk-...",
    name="gpt-4o",
    tasklist="SimpleQA",
    limit=100,
)
```

Works with any OpenAI-compatible endpoint: OpenAI, Anthropic, Azure, Mistral, local deployments, etc.

## Agentic evaluation

For benchmarks where the model uses tools (GAIA, AssistantBench, etc.), you need [Vivarium](https://code.europa.eu/palace/vivarium), a sandboxed Docker runtime for agents.

```bash
pip install vivarium-ai
```

Vivarium starts automatically when you run an agentic tasklist. Requires Docker 24+.

> **Note**: Vivarium is currently pending open-source release (expected within weeks). Contact massimiliano.altieri@ec.europa.eu for early access.

## Creating your own benchmarks

```bash
palace init my-benchmark      # interactive wizard
palace validate my-benchmark  # check for errors
palace publish my-benchmark   # publish to HuggingFace
```

See [Your First Benchmark](https://palace.pages.code.europa.eu/palace-eval/getting-started/first-benchmark/) for a walkthrough.

## Documentation

Full docs at [palace.pages.code.europa.eu/palace-eval](https://palace.pages.code.europa.eu/palace-eval).

## Contributing

Issues and PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Copyright 2025 European Union. Licensed under [EUPL-1.2](https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12).

Developed by the [European Commission Joint Research Centre](https://joint-research-centre.ec.europa.eu/).

## Citation

```bibtex
@software{palace2025,
  title = {PALACE: An Open Benchmark Format for LLM Evaluation},
  author = {Altieri, Massimiliano},
  year = {2025},
  institution = {European Commission Joint Research Centre},
  url = {https://code.europa.eu/palace/palace-eval},
  license = {EUPL-1.2}
}
```

## Contact

- Issues: [GitHub](https://github.com/palace-ai/palace-eval/issues) or [GitLab](https://code.europa.eu/palace/palace-eval/-/issues)
- Email: massimiliano.altieri@ec.europa.eu
