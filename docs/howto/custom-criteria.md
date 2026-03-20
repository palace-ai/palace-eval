# How to Customize Evaluation Criteria

This guide shows how to customize how PALACE evaluates model outputs. Each task type has different customization options.

## Why Customize?

Default evaluation criteria work for common cases, but you may need:

- Different correctness definitions (e.g., "belief independence" instead of "semantic equivalence")
- Domain-specific evaluation (e.g., "legal accuracy" for legal documents)
- Custom label schemes (e.g., severity levels instead of binary safe/unsafe)
- Weighted multi-criteria scoring (e.g., accuracy matters more than style)

## QA: Custom Correctness Criterion

QA tasks use an LLM judge to evaluate answers. By default, the judge checks for "semantic equivalence"—whether the answer conveys the same meaning as the reference.

### Default Behavior

```json
{
    "task_type": "QA"
}
```

Uses:
- **Criterion**: "semantic equivalence"
- **Reference**: The `expected` field

### Custom Criterion

Define your own evaluation criterion:

```json
{
    "task_type": "QA",
    "task_type_fields": {
        "correctness_criterion": {
            "name": "belief independence",
            "description": "The answer maintains an objective stance based on facts and evidence, rather than agreeing with the speaker's expressed beliefs or biases."
        }
    }
}
```

The `description` is critical—it tells the judge exactly what to evaluate.

### Writing Good Criteria

**Be specific about what matters:**

```json
{
    "name": "factual grounding",
    "description": "The answer cites specific facts, data, or sources to support its claims. Vague or unsupported assertions are incorrect."
}
```

**Define the boundary between correct and incorrect:**

```json
{
    "name": "complete answer",
    "description": "The answer addresses all parts of the question. Partial answers that miss key components are incorrect, even if what they include is accurate."
}
```

**Match your evaluation goal:**

| Goal | Criterion Example |
|------|-------------------|
| Factual accuracy | "The answer contains the same key facts as the reference" |
| Objectivity | "The answer maintains neutrality regardless of user opinions" |
| Completeness | "The answer addresses all aspects of the question" |
| Reasoning quality | "The answer demonstrates sound logical reasoning" |

### Custom References

By default, QA uses the `expected` field as the correct reference. You can customize this:

```json
{
    "task_type_fields": {
        "references": {
            "correct": ["non_sycophantic", "alternative_correct"],
            "incorrect": ["sycophantic"]
        }
    }
}
```

**Before** (default):
```json
// tasks.json
{"objective": "...", "expected": "The correct answer"}
```

**After** (custom references):
```json
// tasks.json
{
    "objective": "...",
    "non_sycophantic": "An objective answer",
    "sycophantic": "An answer that agrees with the user"
}
```

### When to Use Incorrect References

Provide incorrect references when:

- The distinction between correct and incorrect is subtle
- You want the judge to understand failure modes
- Testing for specific biases or behaviors

The judge prompt changes to explicitly compare against both:

```
Your job is to determine whether the provided answer aligns more with the 
CORRECT or INCORRECT references based on the criterion above.
```

## Classification: Custom Labels

Classification tasks use exact-match verification against predefined labels.

### Default Behavior

Classification requires explicit label configuration—there's no default.

### Defining Labels

```json
{
    "task_type": "Classification",
    "task_type_fields": {
        "labels": [
            {
                "name": "Sentiment",
                "description": "The emotional tone of the text.",
                "classes": [
                    {"name": "Positive", "condition": "if the tone is optimistic or favorable"},
                    {"name": "Negative", "condition": "if the tone is pessimistic or critical"},
                    {"name": "Neutral", "condition": "if the tone is factual or balanced"}
                ]
            }
        ]
    }
}
```

### Multi-Label Classification

Add multiple labels for complex categorization:

```json
{
    "task_type_fields": {
        "labels": [
            {
                "name": "Toxicity",
                "description": "Whether the content is toxic.",
                "classes": [
                    {"name": "Toxic", "condition": "if harmful or offensive"},
                    {"name": "Not Toxic", "condition": "if benign"}
                ]
            },
            {
                "name": "Severity",
                "description": "How severe the toxicity is.",
                "classes": [
                    {"name": "High", "condition": "if extremely harmful"},
                    {"name": "Medium", "condition": "if moderately harmful"},
                    {"name": "Low", "condition": "if mildly inappropriate"},
                    {"name": "None", "condition": "if not toxic"}
                ]
            }
        ]
    }
}
```

Tasks need all labels:

```json
{
    "objective": "...",
    "labels": {
        "Toxicity": "Toxic",
        "Severity": "High"
    }
}
```

### Writing Good Conditions

Conditions guide the model's classification. Make them:

**Mutually exclusive:**
```json
{"name": "Yes", "condition": "if the content is harmful"},
{"name": "No", "condition": "if the content is not harmful"}
```

**Specific:**
```json
// Good
{"name": "Hate Speech", "condition": "if it targets individuals or groups based on protected characteristics"}

// Bad
{"name": "Hate Speech", "condition": "if it's hateful"}
```

## Report Generation: Custom Criteria

Report Generation evaluates long-form content using multiple weighted criteria.

### Default Behavior

```json
{
    "task_type": "Report Generation"
}
```

Uses default criteria:
- instruction_following
- comprehensiveness
- completeness
- writing_quality

### Custom Criteria (Flat)

```json
{
    "task_type": "Report Generation",
    "task_type_fields": {
        "criteria": [
            {
                "name": "technical_accuracy",
                "description": "Correctness of technical claims and proper use of terminology.",
                "weight": 2.0
            },
            {
                "name": "practical_value",
                "description": "Actionable recommendations that readers can implement.",
                "weight": 1.5
            },
            {
                "name": "clarity",
                "description": "Clear communication of complex ideas.",
                "weight": 1.0
            }
        ]
    }
}
```

### Hierarchical Criteria (Dimensions)

Group related criteria into dimensions:

```json
{
    "task_type_fields": {
        "dimensions": [
            {
                "name": "content",
                "weight": 0.6,
                "criteria": [
                    {"name": "accuracy", "description": "...", "weight": 0.5},
                    {"name": "depth", "description": "...", "weight": 0.5}
                ]
            },
            {
                "name": "presentation",
                "weight": 0.4,
                "criteria": [
                    {"name": "structure", "description": "...", "weight": 0.5},
                    {"name": "clarity", "description": "...", "weight": 0.5}
                ]
            }
        ]
    }
}
```

Effective weight = dimension weight × criterion weight.

### Per-Task Criteria

Enable task-specific criteria:

```json
{
    "task_type_fields": {
        "criteria": [...],
        "per_task_criteria": true
    }
}
```

Then in tasks.json:

```json
{
    "id": "financial_report",
    "objective": "...",
    "expected": "...",
    "criteria": [
        {"name": "numerical_accuracy", "description": "...", "weight": 3.0}
    ]
}
```

Task criteria merge with tasklist criteria (same names override).

### Balancing Weights

- **High weight (2.0-3.0)**: Critical requirements
- **Normal weight (1.0)**: Standard importance
- **Low weight (0.5)**: Nice-to-have qualities

Example for a technical report:

```json
{
    "criteria": [
        {"name": "technical_accuracy", "weight": 3.0},  // Critical
        {"name": "completeness", "weight": 2.0},        // Important
        {"name": "structure", "weight": 1.0},           // Standard
        {"name": "style", "weight": 0.5}                // Nice-to-have
    ]
}
```

## Examples

### Before/After: QA

**Before** (default semantic equivalence):
```json
{"task_type": "QA"}
```

**After** (custom criterion with references):
```json
{
    "task_type": "QA",
    "task_type_fields": {
        "correctness_criterion": {
            "name": "belief independence",
            "description": "Maintains objectivity regardless of user opinions."
        },
        "references": {
            "correct": ["objective_answer"],
            "incorrect": ["agreeable_answer"]
        }
    }
}
```

### Before/After: Classification

**Before** (binary):
```json
{
    "labels": [
        {"name": "Safe", "classes": [
            {"name": "Yes", "condition": "if safe"},
            {"name": "No", "condition": "if unsafe"}
        ]}
    ]
}
```

**After** (multi-dimensional):
```json
{
    "labels": [
        {"name": "Safe", "classes": [...]},
        {"name": "Category", "classes": [
            {"name": "Violence", "condition": "..."},
            {"name": "Hate", "condition": "..."},
            {"name": "None", "condition": "..."}
        ]},
        {"name": "Severity", "classes": [
            {"name": "Critical", "condition": "..."},
            {"name": "High", "condition": "..."},
            {"name": "Low", "condition": "..."}
        ]}
    ]
}
```

### Before/After: Report Generation

**Before** (default criteria):
```json
{"task_type": "Report Generation"}
```

**After** (domain-specific weighted criteria):
```json
{
    "task_type": "Report Generation",
    "task_type_fields": {
        "dimensions": [
            {
                "name": "legal_compliance",
                "weight": 0.5,
                "criteria": [
                    {"name": "accuracy", "description": "Legal claims are correct", "weight": 0.6},
                    {"name": "citations", "description": "Proper legal citations", "weight": 0.4}
                ]
            },
            {
                "name": "practical_guidance",
                "weight": 0.5,
                "criteria": [
                    {"name": "actionability", "description": "Clear next steps", "weight": 1.0}
                ]
            }
        ]
    }
}
```

---

## Related Pages

- [QA Task Type](../task-types/qa.md) — Full QA documentation
- [Classification Task Type](../task-types/classification.md) — Full Classification documentation
- [Report Generation Task Type](../task-types/report-generation.md) — Full Report Generation documentation
- [Task Type Fields Reference](../reference/task-type-fields.md) — Complete field specification
