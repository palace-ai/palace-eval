# PALACE

[![License: EUPL-1.2](https://img.shields.io/badge/License-EUPL--1.2-blue.svg)](https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-orange.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/palace-eval.svg)](https://pypi.org/project/palace-eval/)
[![CI](https://github.com/palace-ai/palace-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/palace-ai/palace-eval/actions/workflows/ci.yml)

<img src="https://code.europa.eu/palace/palace-eval/-/raw/main/assets/readme_images/logo.png" width="280" alt="PALACE logo">

**PALACE** is an open benchmark format for LLM evaluation, with native support for agentic tasks.

Benchmarks should be portable. A PALACE benchmark is a self-contained folder with two JSON files: `info.json` (metadata and evaluation config) and `tasks.json` (the actual tasks). No framework lock-in, no Python decorators, no code to run. Just data that any tool can read.

`palace-eval` is the reference implementation.

## Why another benchmark format?

Most benchmarks today are tied to specific frameworks. LM-eval-harness tasks are Python code. Inspect-AI uses `@task` decorators. If you want to run a benchmark, you need their infrastructure.

PALACE takes a different approach:

- **Self-contained**: everything travels together (tasks, expected outputs, judge criteria, evaluation logic)
- **HuggingFace-distributed**: download with `palace-download`, standard hosting and discovery  
- **Agentic-native**: tool-using agents are a first-class task type
- **Framework-agnostic**: palace-eval runs them, but so could anything else

We ship 27+ benchmarks covering reasoning, knowledge, safety, multilingual, multimodal, and agentic capabilities.

## The format

A PALACE benchmark looks like this:

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
  "format_version": "1.0",
  "task_type": "QA",
  "category": "Knowledge",
  "task_type_fields": {
    "correctness_criterion": {
      "name": "semantic equivalence",
      "description": "The answer is semantically equivalent to the reference"
    }
  }
}
```

**tasks.json** contains the tasks:

```json
[
  {
    "id": "q1",
    "objective": "What is the capital of France?",
    "references": {"correct": ["Paris"]}
  },
  {
    "id": "q2", 
    "objective": "Who wrote Romeo and Juliet?",
    "references": {"correct": ["William Shakespeare", "Shakespeare"]}
  }
]
```

That's it. The format supports five task types (QA, Classification, Criteria Evaluation, Instruction Following, and Agentic), each with its own verification logic. See the [docs](https://palace.pages.code.europa.eu/palace-eval) for the full spec.

## Quick start

Install from PyPI:

```bash
pip install palace-eval
```

Download a benchmark and run it:

```bash
palace-download -t SimpleQA
palace-run -u https://api.openai.com/v1 -k $OPENAI_API_KEY -m gpt-4o -t SimpleQA -l 20
```

Results go to `~/.cache/palace/results/`.

## Running evaluations

Three ways to use it:

**Interactive CLI** (walks you through the options):

```bash
palace-cli
```

**Direct command** (for scripting):

```bash
palace-run \
  -u https://api.openai.com/v1 \
  -k $OPENAI_API_KEY \
  -m gpt-4o \
  -t SimpleQA \
  -l 50
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

Works with any OpenAI-compatible endpoint: OpenAI, Anthropic, Mistral, local deployments, etc.

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

Download all of them:

```bash
palace-download
```

Or specific ones:

```bash
palace-download -t SimpleQA MMLU GPQA-Diamond
```

## Agentic evaluation

For benchmarks where the model uses tools (GAIA, AssistantBench, etc.), you need [Vivarium](https://github.com/vivarium-ai/vivarium), a sandboxed Docker runtime for agents.

```bash
pip install vivarium-ai
```

Vivarium starts automatically when you run an agentic tasklist. Requires Docker 24+.

> **Note**: Vivarium is currently pending open-source release (expected within weeks). Contact massimiliano.altieri@ec.europa.eu for early access.

## Creating your own benchmarks

Add a folder to `~/.cache/palace/tasklists/`:

```
MyBenchmark/
├── info.json
└── tasks.json
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
