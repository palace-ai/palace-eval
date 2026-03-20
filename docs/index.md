# PALACE Documentation

**PALACE** (Platform for Automated LLMs Agentic Capabilities Evaluation) is a framework for evaluating LLM capabilities through configurable benchmarks.

## Quick Links

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Getting Started**

    ---

    Install PALACE and create your first benchmark in minutes.

    [:octicons-arrow-right-24: Get started](getting-started/index.md)

-   :material-format-list-checks:{ .lg .middle } **Task Types**

    ---

    Learn about QA, Classification, and Report Generation task types.

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

- **QA tasks** - Verify factual correctness with LLM judges
- **Classification tasks** - Exact-match categorical outputs
- **Report Generation tasks** - Pairwise comparison of long-form content

## Three Task Types

| Task Type | Use Case | Verification |
|-----------|----------|--------------|
| [QA](task-types/qa.md) | Factual questions, open-ended answers | LLM judge with configurable criteria |
| [Classification](task-types/classification.md) | Categorical outputs, labels | Exact match against expected labels |
| [Report Generation](task-types/report-generation.md) | Long-form documents, reports | Pairwise comparison with weighted criteria |

## Getting Help

- [Glossary](glossary.md) - Definitions of key terms
- [Examples](examples/index.md) - Real-world benchmark patterns
- [Concepts](concepts/index.md) - How PALACE works under the hood
