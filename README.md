# PALACE

[![License: EUPL-1.2](https://img.shields.io/badge/License-EUPL--1.2-blue.svg)](https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-orange.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/palace-eval.svg)](https://pypi.org/project/palace-eval/)
[![CI](https://github.com/palace-ai/palace-eval/actions/workflows/ci.yml/badge.svg)](https://github.com/palace-ai/palace-eval/actions/workflows/ci.yml)

A platform for evaluating LLM capabilities across diverse benchmarks, with native support for agentic evaluation.

<img src="https://code.europa.eu/palace/palace-eval/-/raw/main/assets/readme_images/logo.png" width="300" alt="PALACE logo">

## Overview

**PALACE** (**P**latform for **A**utomated **L**LMs **A**gentic **C**apabilities **E**valuation) is an open-source evaluation framework developed by the [European Commission Joint Research Centre](https://joint-research-centre.ec.europa.eu/).

Key features:

- **27+ vetted benchmarks** covering reasoning, knowledge, safety, multilingual, multimodal, and agentic capabilities
- **Standardized format** - portable JSON-based tasklist format, distributed via HuggingFace
- **Agentic-native** — first-class support for tool-using agents via [Vivarium](https://github.com/vivarium-ai/vivarium) runtime
- **Any OpenAI-compatible endpoint** - evaluate models from OpenAI, Anthropic, Mistral, local deployments, or any compatible API

## Installation

### From PyPI (recommended)

```bash
pip install palace-eval
```

Or with [uv](https://github.com/astral-sh/uv) (faster):

```bash
uv pip install palace-eval
```

### From source

```bash
git clone https://code.europa.eu/palace/palace-eval.git
cd palace-eval
uv sync        # recommended
# or: pip install -e .
```

### Requirements

- Python 3.13+
- An OpenAI-compatible API endpoint and key

### Agentic evaluation (optional)

For agentic benchmarks (GAIA, AssistantBench, etc.), you also need:

- Docker 24+
- The [Vivarium](https://github.com/vivarium-ai/vivarium) SDK

> **Note**: Vivarium is currently pending open-source release (expected within weeks). The GitHub link above is not yet active. If you need agentic evaluation now, please contact massimiliano.altieri@ec.europa.eu for early access.

Install Vivarium:

```bash
pip install vivarium-ai
```

Vivarium starts automatically when you run an agentic tasklist.

## Quick Start

```bash
# 1. Download a benchmark tasklist
palace-download -t SimpleQA

# 2. Run evaluation
palace-run -u https://api.openai.com/v1 -k $OPENAI_API_KEY -m gpt-4o -t SimpleQA -l 20
```

Results are saved to `~/.cache/palace/results/`.

## Usage

### Interactive CLI

```bash
palace-cli
```

Guides you through selecting endpoint, model, benchmarks, and run configuration.

### Direct command

```bash
palace-run \
   -u https://api.openai.com/v1 \
   -k $OPENAI_API_KEY \
   -m gpt-4o \
   -t SimpleQA \
   -l 50
```

See `palace-run --help` for all options.

### Programmatic API

```python
from palace import evaluate

evaluate(
    run_name="my-evaluation",
    url="https://api.openai.com/v1",
    token="sk-...",
    name="gpt-4o",
    tasklist="SimpleQA",
    limit=100,
)
```

## Supported Benchmarks

PALACE includes 27+ benchmarks across multiple categories:


| Category                  | Benchmarks                                                   |
| --------------------------- | -------------------------------------------------------------- |
| **Knowledge & Reasoning** | SimpleQA, HotpotQA, Humanity's Last Exam, GPQA Diamond, MUSR |
| **Academic & Math**       | MMLU, MMLU-Pro, MATH-500, AIME 2025, BBH, HellaSwag          |
| **Multilingual**          | MMMLU (14 languages), MGSM, Belebele (122 languages)         |
| **Long Context**          | BABILong (4k-128k), LongBench v2                             |
| **Multimodal**            | MMMU, MMMU Pro, VLSBench                                     |
| **Instruction Following** | IFEval                                                       |
| **Agentic**               | GAIA, AssistantBench                                         |

Download benchmarks with:

```bash
palace-download                    # all benchmarks
palace-download -t SimpleQA MMLU   # specific benchmarks
```

Some benchmarks (marked with a lock icon in the docs) require a [HuggingFace token](https://huggingface.co/settings/tokens) for gated datasets.

## Tasklist Format

PALACE uses a standardized, portable JSON format for benchmarks:

```
<tasklist_name>/
+-- info.json      # metadata: task type, category, modalities
+-- tasks.json     # list of evaluation tasks
+-- task_files/    # optional: attachments (images, documents)
```

Create custom benchmarks by adding folders to `~/.cache/palace/tasklists/`.

## Documentation

Full documentation: [https://palace.pages.code.europa.eu/palace-eval](https://palace.pages.code.europa.eu/palace-eval)

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Copyright (C) 2025 European Union

Licensed under the [European Union Public Licence (EUPL) v. 1.2](https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12).

See [LICENSE](LICENSE) and [NOTICE](NOTICE) for details.

## Citation

If you use PALACE in your research, please cite:

```bibtex
@software{palace2025,
  title = {PALACE: Platform for Automated LLMs Agentic Capabilities Evaluation},
  author = {Altieri, Massimiliano},
  year = {2025},
  institution = {European Commission Joint Research Centre},
  url = {https://code.europa.eu/palace/palace-eval},
  license = {EUPL-1.2}
}
```

## Support

- **Issues**: [GitHub Issues](https://github.com/palace-ai/palace-eval/issues) (preferred) or [GitLab Issues](https://code.europa.eu/palace/palace-eval/-/issues)
- **Email**: massimiliano.altieri@ec.europa.eu
