# How-To Guides

Task-oriented guides for accomplishing specific goals with PALACE. Each guide focuses on a single task and provides step-by-step instructions.

## Available Guides

### [Run Evaluations](run-evaluations.md)

Run PALACE evaluations using the interactive CLI, command-line interface, or programmatic API. Covers batch processing and output interpretation.

**You'll learn**: CLI options, Python API, batch evaluation patterns, result analysis.

### [Custom Criteria](custom-criteria.md)

Customize how PALACE evaluates model outputs. Configure correctness criteria for QA, design label schemes for Classification, and set up weighted criteria for Report Generation.

**You'll learn**: Custom QA criteria, Classification labels, Report Generation dimensions, before/after examples.

### [Publish to HuggingFace](publish-huggingface.md)

Share your benchmark with the community by publishing to HuggingFace. Covers authentication, upload process, and documentation best practices.

**You'll learn**: HuggingFace setup, upload commands, README templates, versioning.

### [Debug Evaluations](debug-evaluations.md)

Troubleshoot common issues when running evaluations. Diagnose task failures, inspect prompts, and compare results across runs.

**You'll learn**: Task isolation, JSON validation, judge debugging, result comparison.

### [Migration Guide](migration.md)

Migrate tasklists from deprecated task types (MLC, Sycophancy-Binary, Sycophancy-OpenEnded, Long Context QA, Claim Verification) to the current PALACE format.

**You'll learn**: MLC → Classification, Sycophancy → QA/Classification, Long Context QA → QA, field mapping.

### [Add Public Benchmark](add-public-benchmark.md)

Add support for a new public HuggingFace benchmark to PALACE's automatic download system.

**You'll learn**: Dataset exploration, column mapping, attachment handling, Classification configuration.

### [Model Adapters](model-adapters.md)

Evaluate specialized finetuned models (guardrails, classifiers) that can't follow PALACE's standard prompt format. Define per-model input/output transformations via YAML config.

**You'll learn**: Adapter YAML schema, input templates, output regex parsing, value mapping, glob matching, gradin integration.

## Quick Reference

| I want to... | Guide |
|--------------|-------|
| Run an evaluation | [Run Evaluations](run-evaluations.md) |
| Change how correctness is judged | [Custom Criteria](custom-criteria.md) |
| Share my benchmark | [Publish to HuggingFace](publish-huggingface.md) |
| Fix failing tasks | [Debug Evaluations](debug-evaluations.md) |
| Update an old tasklist | [Migration Guide](migration.md) |
| Add a public HuggingFace benchmark | [Add Public Benchmark](add-public-benchmark.md) |
| Evaluate specialized finetuned models | [Model Adapters](model-adapters.md) |

---

## Related Pages

- [Getting Started](../getting-started/index.md) — New to PALACE? Start here
- [Task Types](../task-types/index.md) — Understanding QA, Classification, Report Generation
- [Reference](../reference/index.md) — Technical specifications
