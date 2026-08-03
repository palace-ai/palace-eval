# Changelog

All notable changes to PALACE will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.0.0]: https://github.com/palace-ai/palace-eval/releases/tag/v1.0.0
