# Examples

Real-world benchmark patterns you can learn from and adapt. Each example shows a complete, working tasklist configuration with explanations of design decisions.

## Choosing an Example

| Example | Task Type | Use Case | Complexity |
|---------|-----------|----------|------------|
| [Factual QA](factual-qa.md) | QA | Testing factual knowledge | Simple |
| [Safety Classification](safety-classification.md) | Classification | Content moderation | Simple |
| [Sycophancy](sycophancy.md) | Both | Detecting model bias | Medium |
| [Research Reports](research-reports.md) | Criteria Evaluation | Long-form evaluation | Advanced |

## Start Here

**New to PALACE?** Start with [Factual QA](factual-qa.md)—it's the simplest pattern and demonstrates core concepts.

**Building a classifier?** See [Safety Classification](safety-classification.md) for the Classification task type pattern.

**Need nuanced evaluation?** [Sycophancy](sycophancy.md) shows how to use custom criteria and both task types for the same evaluation goal.

**Evaluating long content?** [Research Reports](research-reports.md) demonstrates hierarchical criteria for comprehensive assessment.

## Example Summaries

### Factual QA

Tests whether a model can correctly answer factual questions. Uses default semantic equivalence—no custom configuration needed.

**Pattern**: Simple QA with `expected` field as reference.

```json
{"task_type": "QA"}
```

[View Example →](factual-qa.md)

### Safety Classification

Evaluates whether a model can identify potentially harmful content. Binary classification with exact-match verification.

**Pattern**: Classification with custom labels and classes.

```json
{
    "task_type": "Classification",
    "task_type_fields": {
        "labels": [{"name": "Unsafe", "classes": [...]}]
    }
}
```

[View Example →](safety-classification.md)

### Sycophancy Evaluation

Tests whether models maintain objectivity when users express opinions. Shows two complementary approaches:

- **Classification**: Binary detection of correct vs. sycophantic answers
- **QA**: Open-ended evaluation with custom "belief independence" criterion

**Pattern**: Custom criteria with correct and incorrect references.

```json
{
    "task_type": "QA",
    "task_type_fields": {
        "correctness_criterion": {"name": "belief independence", ...},
        "references": {"correct": ["non_sycophantic"], "incorrect": ["sycophantic"]}
    }
}
```

[View Example →](sycophancy.md)

### Research Reports

Evaluates long-form research reports using hierarchical criteria organized into dimensions. Demonstrates weighted multi-criteria assessment.

**Pattern**: Criteria Evaluation with dimensions and nested criteria.

```json
{
    "task_type": "Criteria Evaluation",
    "task_type_fields": {
        "dimensions": [
            {"name": "content_quality", "weight": 0.5, "criteria": [...]},
            {"name": "presentation", "weight": 0.3, "criteria": [...]}
        ]
    }
}
```

[View Example →](research-reports.md)

## Common Patterns

### Minimal Configuration

For simple evaluations, you often don't need `task_type_fields`:

```json
{"task_type": "QA"}  // Uses default semantic equivalence
```

### Custom Criteria

When default evaluation doesn't fit your needs:

```json
{
    "task_type_fields": {
        "correctness_criterion": {
            "name": "your criterion",
            "description": "What the judge should evaluate"
        }
    }
}
```

### Multi-Label Classification

For complex categorization:

```json
{
    "task_type_fields": {
        "labels": [
            {"name": "Label1", "classes": [...]},
            {"name": "Label2", "classes": [...]}
        ]
    }
}
```

### Weighted Criteria

For nuanced scoring:

```json
{
    "task_type_fields": {
        "criteria": [
            {"name": "important", "weight": 2.0, ...},
            {"name": "secondary", "weight": 1.0, ...}
        ]
    }
}
```

---

## Related Pages

- [Task Types Overview](../task-types/index.md) — Understanding QA, Classification, and Criteria Evaluation
- [Your First Benchmark](../getting-started/first-benchmark.md) — Step-by-step tutorial
- [Task Type Fields Reference](../reference/task-type-fields.md) — Complete configuration options
