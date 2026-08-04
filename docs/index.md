# PALACE Documentation

**PALACE** (Platform for Automated LLMs Agentic Capabilities Evaluation) is an open benchmark format for LLM evaluation, with native support for agentic tasks. `palace-eval` is the reference implementation.

## Quick Links

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Getting Started**

    ---

    Install PALACE and create your first benchmark in minutes.

    [:octicons-arrow-right-24: Get started](getting-started/index.md)

-   :material-format-list-checks:{ .lg .middle } **Task Types**

    ---

    Learn about the five task types: QA, Classification, Criteria Evaluation, Instruction Following, and Agentic.

    [:octicons-arrow-right-24: Explore task types](task-types/index.md)

-   :material-book-open-variant:{ .lg .middle } **How-To Guides**

    ---

    Step-by-step guides for common tasks.

    [:octicons-arrow-right-24: Browse guides](howto/index.md)

-   :material-file-document:{ .lg .middle } **Reference**

    ---

    Complete specifications and API documentation.

    [:octicons-arrow-right-24: View reference](reference/index.md)

</div>

## What is PALACE?

PALACE evaluates LLM agents across configurable benchmarks. It supports:

- **QA tasks** — Verify factual correctness with LLM judges
- **Classification tasks** — Exact-match categorical outputs
- **Criteria Evaluation tasks** — Pairwise comparison of long-form content
- **Instruction Following tasks** — Verify structured output constraints
- **Agentic tasks** — Tool-using agents in sandboxed environments

## Five Task Types

| Task Type | Use Case | Verification |
|-----------|----------|--------------|
| [QA](task-types/qa.md) | Factual questions, open-ended answers | LLM judge with configurable criteria |
| [Classification](task-types/classification.md) | Categorical outputs, labels | Exact match against expected labels |
| [Criteria Evaluation](task-types/criteria-evaluation.md) | Long-form documents, reports | Pairwise comparison with weighted criteria |
| [Instruction Following](task-types/instruction-following.md) | Structured output formats | Constraint verification (length, format, keywords) |
| [Agentic](task-types/agentic.md) | Tool-using agents, coding, web tasks | External verifier in sandboxed environment |

## Getting Help

- [Glossary](glossary.md) - Definitions of key terms
- [Examples](examples/index.md) - Real-world benchmark patterns
- [Concepts](concepts/index.md) - How PALACE works under the hood
