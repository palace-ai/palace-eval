# Reference

Technical specifications and complete documentation for PALACE configuration and output formats.

## Official Tasklists

### [Official PALACE Tasklists](tasklists/index.md)

Comprehensive documentation for the official benchmark tasklists developed by the JRC AI team:

- [GuardBench](tasklists/guardbench.md) — Multilingual safety content classification
- [RTVLM](tasklists/rtvlm.md) — Multimodal red-teaming safety classification
- [VLGuard](tasklists/vlguard.md) — Multimodal safety with paired safe/unsafe instructions
- [MM-SafetyBench](tasklists/mmsafetybench.md) — Adversarial image jailbreak stress test
- [Sycophancy](tasklists/sycophancy.md) — Sycophancy detection in two modalities
- [ValuesEval24](tasklists/valueseval24.md) — Human values detection across 9 languages
- [DocRetrieval](tasklists/docretrieval.md) — Multi-document retrieval and synthesis
- [DeepConsult](tasklists/deepconsult.md) — Long-form consulting report generation
- [DeepResearchBench](tasklists/deepresearchbench.md) — Research reports with per-task criteria

### [Public Benchmarks](public-benchmarks.md)

Public HuggingFace benchmarks supported by `palace-download`:

- BABILong (32k/128k), CURIE-protein, HotpotQA, GAIA, SimpleQA, SimpleQA-Verified, AssistantBench, Humanity's Last Exam, VLSBench

## Specifications

### [info.json](info-json.md)

Complete specification for tasklist metadata files. Covers required fields, optional fields, and task-type-specific configuration.

### [tasks.json](tasks-json.md)

Complete specification for task files. Documents common fields and task-type-specific requirements.

### [Task Type Fields](task-type-fields.md)

Detailed documentation of `task_type_fields` configuration for each task type:

- QA: `correctness_criterion`, `references`
- Classification: `labels`
- Criteria Evaluation: `criteria`, `dimensions`, `per_task_criteria`
- Instruction Following: constraints defined per task
- Agentic: Vivarium spec configuration

### [Output Metrics](metrics.md)

Complete specification for evaluation output format. Covers JSONL structure, per-task metrics, and aggregate calculations.

### [CLI Reference](cli.md)

Command-line interface documentation for `palace-cli`, `palace-run`, and `palace-download`.

## Cheatsheets

Printable quick-reference documents (A3 landscape PDFs):

- **[Reference Sheet](https://code.europa.eu/palace/palace-eval/-/blob/main/cheatsheets/reference-sheet.pdf)** — Complete reference for all 5 task types, JSON schemas, and common patterns
- **[Agentic Tutorial](https://code.europa.eu/palace/palace-eval/-/blob/main/cheatsheets/agentic-tutorial.pdf)** — Step-by-step guide for building an agentic benchmark

Source files are in [`cheatsheets/`](https://code.europa.eu/palace/palace-eval/-/tree/main/cheatsheets) if you want to rebuild or contribute.

## Quick Reference

### Minimal info.json

```json
{
    "name": "MyBenchmark",
    "id": "my-org/MyBenchmark",
    "task_type": "QA"
}
```

### Minimal tasks.json

```json
[
    {"id": "task_001", "objective": "Question?", "expected": "Answer"}
]
```

### Task Types

| Type | Verification | Configuration |
|------|--------------|---------------|
| QA | LLM judge | `correctness_criterion`, `references` |
| Classification | Exact match | `labels` (required) |
| Criteria Evaluation | LLM judge | `criteria` or `dimensions` |
| Instruction Following | Deterministic | `constraints` per task |
| Agentic | External verifier | Vivarium spec |

### CLI Commands

| Command | Purpose |
|---------|---------|
| `palace-cli` | Interactive interface |
| `palace-run -u URL -m NAME -t TASKLIST` | Run evaluation |
| `palace-download` | Download tasklists |

---

## Related Pages

- [Task Types](../task-types/index.md) — Understanding task types
- [Examples](../examples/index.md) — Real-world configurations
- [How-To Guides](../howto/index.md) — Task-oriented guides
