# Reference

Technical specifications and complete documentation for PALACE configuration and output formats.

## Official Tasklists

### [Official PALACE Tasklists](tasklists/index.md)

Comprehensive documentation for the official benchmark tasklists developed by the JRC AI team:

- [GuardBench](tasklists/guardbench.md) — Multilingual safety content classification
- [Sycophancy](tasklists/sycophancy.md) — Sycophancy detection in two modalities
- [ValuesEval24](tasklists/valueseval24.md) — Human values detection across 9 languages
- [DocRetrieval](tasklists/docretrieval.md) — Multi-document retrieval and synthesis
- [DeepConsult](tasklists/deepconsult.md) — Long-form consulting report generation
- [DeepResearchBench](tasklists/deepresearchbench.md) — Research reports with per-task criteria

### [Public Benchmarks](public-benchmarks.md)

Public HuggingFace benchmarks supported by `palace-download`:

- BABILong (32k/128k), CURIE-protein, HotpotQA, GAIA, SimpleQA, AssistantBench, Humanity's Last Exam, VLSBench

## Specifications

### [info.json](info-json.md)

Complete specification for tasklist metadata files. Covers required fields, optional fields, and task-type-specific configuration.

### [tasks.json](tasks-json.md)

Complete specification for task files. Documents common fields and task-type-specific requirements.

### [Task Type Fields](task-type-fields.md)

Detailed documentation of `task_type_fields` configuration for each task type:

- QA: `correctness_criterion`, `references`
- Classification: `labels`
- Report Generation: `criteria`, `dimensions`, `per_task_criteria`

### [Output Metrics](metrics.md)

Complete specification for evaluation output format. Covers JSONL structure, per-task metrics, and aggregate calculations.

### [CLI Reference](cli.md)

Command-line interface documentation for `palace-cli`, `palace-run`, and `palace-download`.

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
| Report Generation | LLM pairwise | `criteria` or `dimensions` |

### CLI Commands

| Command | Purpose |
|---------|---------|
| `palace-cli` | Interactive interface |
| `palace-run -u URL -m NAME -t TASKLIST` | Run evaluation |
| `palace-download` | Download tasklists |
| `palace-mcpstart` | Start MCP server |

---

## Related Pages

- [Task Types](../task-types/index.md) — Understanding task types
- [Examples](../examples/index.md) — Real-world configurations
- [How-To Guides](../howto/index.md) — Task-oriented guides
