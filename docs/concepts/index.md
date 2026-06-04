# Concepts

Understanding-oriented explanations of how PALACE works internally. These pages help you understand the "why" behind PALACE's design.

## Available Topics

### [Evaluation Pipeline](evaluation-pipeline.md)

How PALACE evaluates models from start to finish. Covers the complete flow from loading a tasklist to producing results.

**You'll learn**: Pipeline stages, customization points, error handling.

### [Verification Methods](verification.md)

The different ways PALACE verifies model outputs. Compares LLM judges, exact matching, and pairwise comparison.

**You'll learn**: When to use each method, trade-offs, configuration options.

### [LLM Judges](llm-judges.md)

How PALACE uses language models to evaluate responses. Covers judge prompts, configuration, and best practices.

**You'll learn**: Judge behavior, prompt structure, debugging tips.

## Key Concepts

### Task Types

PALACE supports three task types, each with different verification:

| Task Type | Verification | Use Case |
|-----------|--------------|----------|
| QA | LLM judge | Factual questions, semantic matching |
| Classification | Exact match | Categorical outputs, safety filters |
| Criteria Evaluation | Pairwise comparison | Long-form content, multi-criteria |

### Tasklists

A tasklist is a benchmark consisting of:

- `info.json` — Metadata and configuration
- `tasks.json` — Tasks to evaluate

Tasklists are stored in `~/.cache/palace/tasklists/`.

### Verification

Verification determines if a model's output is correct:

- **Semantic**: Does it mean the same thing? (QA)
- **Exact**: Does it match exactly? (Classification)
- **Comparative**: Is it better than the reference? (Criteria Evaluation)

### Judges

LLM judges evaluate outputs that can't be verified with simple matching. They:

- Understand semantic equivalence
- Apply custom criteria
- Provide reasoning for decisions

---

## Related Pages

- [Task Types](../task-types/index.md) — Practical task type guides
- [Reference](../reference/index.md) — Technical specifications
- [Examples](../examples/index.md) — Real-world patterns
