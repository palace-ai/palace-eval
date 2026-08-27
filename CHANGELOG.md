# Changelog

All notable changes to PALACE will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.5] - 2026-08-27

### Added
- Interactive wizard mode: `palace run` with no arguments launches a guided setup for model selection, tasklist selection, and evaluation options

## [1.0.4] - 2026-08-26

### Fixed
- Wrong model name now caught upfront for all run modes (not just non-agentic), before any tasks run
- Vivarium connectivity checked immediately on startup — wrong URL fails fast with a clear error instead of hanging

## [1.0.3] - 2026-08-26

### Fixed
- `palace run --agentic` now correctly reads `vivarium_url` from config file / `VIVARIUM_URL` env var instead of always auto-starting a local vivarium
- `palace config set` now warns when an env var or `.env` file is shadowing the key being set, and identifies the source file

### Added
- `--vivarium-url` option on `palace run` to override the vivarium service URL per-run



### Fixed
- `palace run --agentic` now correctly reads `vivarium_url` from config file / `VIVARIUM_URL` env var instead of always auto-starting a local vivarium
- `palace config set` now warns when an env var (or `.env` file) is shadowing the key being set

### Added
- `--vivarium-url` option on `palace run` to override the vivarium service URL per-run

## [1.0.2] - 2026-08-24

### Fixed
- API key now optional for endpoints that don't require authentication
- Judge URL can now be configured separately from model URL
- Improved error messages for malformed URLs or unavailable model names
- Tasklist name resolution for `org--name` folder format

### Changed
- Improved `config unset` command messages
- Now showing results path after evaluation completes

### Added
- `--param` / `-p` option for `palace run` to pass extra model parameters

## [1.0.1] - 2026-08-05

### Added
- Unified `palace` CLI replacing fragmented entrypoints (`palace-cli`, `palace-run`, `palace-download`)
- `palace config set/get/unset` for persistent configuration in `~/.config/palace/config.yaml`
- `palace config env` to show environment variable mappings for CI/Docker
- Tag-based benchmark discovery from HuggingFace and GitHub
- Custom source management via `palace sources add/rm`
- Tasklist authoring tools: `palace init`, `palace validate`, `palace publish`

### Changed
- Configuration priority: CLI flags > environment variables > config file
- Old entrypoints (`palace-cli`, `palace-run`, `palace-download`) now show deprecation banner

### Fixed
- Pin `mcp<2` to avoid breaking API change
- Updated URLs to code.europa.eu

## [1.0.0] - 2025-08-03

### Added
- Initial open-source release under EUPL-1.2 license
- 27+ vetted benchmark tasklists covering reasoning, knowledge, safety, multilingual, multimodal, and agentic capabilities
- Five task types: QA, Classification, CriteriaEvaluation, InstructionFollowing, Agentic
- HuggingFace-based tasklist distribution via `palace-download`
- Three usage modes: interactive CLI (`palace-cli`), direct command (`palace-run`), programmatic API (`from palace import evaluate`)
- Agentic evaluation support via Vivarium runtime integration
- Concurrent task evaluation with configurable parallelism
- LLM-based judge for answer verification
- I/O adapters for specialized model formats
- Support for multimodal inputs (images, audio, documents)
- 4-state evaluation outcomes (correct, incorrect, error, unsupported)
- Long-context benchmark support (BABILong, LongBench v2, RULER)

### Benchmarks included
- **Knowledge & Reasoning**: SimpleQA, SimpleQA-Verified, HotpotQA, Humanity's Last Exam, SuperGPQA, GPQA Diamond, MUSR
- **Academic & Math**: MMLU, MMLU-Pro, MATH-500, AIME 2025, BBH, HellaSwag
- **Multilingual**: MMMLU, MGSM, Belebele
- **Long Context**: BABILong (4k-128k), LongBench v2
- **Multimodal**: MMMU, MMMU Pro, VLSBench
- **Instruction Following**: IFEval
- **Agentic**: GAIA, AssistantBench
- **Domain-Specific**: CURIE-protein

[1.0.2]: https://code.europa.eu/palace/palace-eval/-/releases/v1.0.2
[1.0.1]: https://code.europa.eu/palace/palace-eval/-/releases/v1.0.1
[1.0.0]: https://code.europa.eu/palace/palace-eval/-/releases/v1.0.0
