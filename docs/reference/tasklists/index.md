# Official PALACE Tasklists

This section documents the official benchmark tasklists developed by the JRC AI team. These tasklists are designed to evaluate specific capabilities of large language models, from safety classification to complex research report generation.

Most official tasklists are available on HuggingFace under the `jrc-ai` organization and can be downloaded using `palace download`. Multimodal safety benchmarks (RTVLM, VLGuard, MM-SafetyBench) use conversion scripts instead — see their individual pages for setup instructions.

## Overview

The official PALACE tasklists span multiple task types and cover a diverse range of evaluation scenarios:

| Tasklist | Task Type | Category | Tasks | Description |
|----------|-----------|----------|------:|-------------|
| [GuardBench](guardbench.md) | Classification | Safety | 30,852+ | Multilingual safety content classification |
| [RTVLM](rtvlm.md) | Classification | Safety | 921 | Multimodal red-teaming safety classification |
| [VLGuard](vlguard.md) | Classification | Safety | 1,558 | Multimodal safety with paired safe/unsafe instructions |
| [MM-SafetyBench](mmsafetybench.md) | Classification | Safety | 5,040 | Adversarial image jailbreak stress test |
| [Sycophancy](sycophancy.md) | Classification / QA | Reliability | 26,188 | Sycophancy detection in two modalities |
| [ValuesEval24](valueseval24.md) | Classification | Alignment | 14,904 | Human values detection across 9 languages |
| [DocRetrieval](docretrieval.md) | QA | Agentic | 1,420 | Multi-document retrieval and synthesis |
| [DeepConsult](deepconsult.md) | Criteria Evaluation | Criteria Evaluation | 102 | Long-form consulting report generation |
| [DeepResearchBench](deepresearchbench.md) | Criteria Evaluation | Deep Research | 50 | Research reports with per-task criteria |

## Downloading Tasklists

Use `palace download` to fetch any official tasklist:

```bash
# Interactive selection
palace download

# Direct download by name
palace download GuardBench-EN
palace download DeepResearchBench
```

Tasklists are cached in `~/.cache/palace/tasklists/` and can be used immediately with `palace run` or `palace`.

## Design Principles

The official PALACE tasklists share several design principles:

1. **Grounded in real-world needs**: Each tasklist addresses a genuine evaluation challenge faced by practitioners deploying LLMs in production.

2. **Rigorous construction**: Tasks are generated through systematic pipelines with validation steps to ensure quality and consistency.

3. **Multilingual where appropriate**: Several tasklists include multiple languages to support evaluation of multilingual models.

4. **Configurable evaluation**: Task types and criteria are defined in `info.json`, allowing the same evaluation framework to handle diverse benchmarks.

5. **Reproducible**: All tasklists are versioned and available through HuggingFace for reproducible research.

## Tasklist Categories

### Safety & Reliability

- **[GuardBench](guardbench.md)**: Tests whether models can identify unsafe or potentially harmful content across five European languages.
- **[RTVLM](rtvlm.md)**: Tests whether multimodal guardrail models can identify unsafe content in image+text inputs, including jailbreak images, sensitive photographs, and misleading visuals.
- **[VLGuard](vlguard.md)**: Tests whether models can determine safety when the same image is paired with both safe and unsafe instructions.
- **[MM-SafetyBench](mmsafetybench.md)**: Pure adversarial stress test — every task is a jailbreak attempt using query-relevant images across 13 harmful scenarios.
- **[Sycophancy](sycophancy.md)**: Evaluates whether models maintain objectivity when users express opinions, rather than agreeing with stated beliefs.

### Alignment & Values

- **[ValuesEval24](valueseval24.md)**: Assesses model ability to detect human values in text, based on Schwartz's theory of basic human values.

### Agentic Capabilities

- **[DocRetrieval](docretrieval.md)**: Tests document retrieval and multi-document reasoning using real EU legal documents.

### Long-Form Generation

- **[DeepConsult](deepconsult.md)**: Evaluates generation of comprehensive consulting reports on complex business and policy topics.
- **[DeepResearchBench](deepresearchbench.md)**: Assesses research report quality using task-specific hierarchical evaluation criteria.

---

## Related Pages

- [Task Types Overview](../task-types/index.md) — Understanding QA, Classification, and Criteria Evaluation
- [info.json Reference](../info-json.md) — Complete specification for tasklist metadata
- [tasks.json Reference](../tasks-json.md) — Complete specification for task files
