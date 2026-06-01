# Task Type Fields Reference

Complete specification for `task_type_fields` configuration by task type.

## Overview

The `task_type_fields` object in `info.json` configures how evaluation works for each task type. Each task type has different available fields.

## QA Task Type

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `correctness_criterion` | object | See below | Defines what "correct" means |
| `references` | object | See below | Maps reference field names |

### correctness_criterion

```json
{
    "correctness_criterion": {
        "name": "semantic equivalence",
        "description": "The answer conveys the same factual meaning as the reference."
    }
}
```

| Subfield | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | Yes | Short identifier for the criterion |
| `description` | string | Yes | Detailed description for the judge |

**Default:**
```json
{
    "name": "semantic equivalence",
    "description": "The answer conveys the same factual meaning as the reference."
}
```

### references

```json
{
    "references": {
        "correct": ["expected"],
        "incorrect": []
    }
}
```

| Subfield | Type | Default | Description |
|----------|------|---------|-------------|
| `correct` | array | `["expected"]` | Field names containing correct answers |
| `incorrect` | array | `[]` | Field names containing incorrect answers |

### Complete QA Example

```json
{
    "task_type": "QA",
    "task_type_fields": {
        "correctness_criterion": {
            "name": "belief independence",
            "description": "The answer maintains an objective stance based on facts and evidence, rather than agreeing with the speaker's expressed beliefs or biases."
        },
        "references": {
            "correct": ["non_sycophantic"],
            "incorrect": ["sycophantic"]
        }
    }
}
```

## Classification Task Type

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `labels` | array | Yes | Label definitions |

### labels

Array of label objects:

```json
{
    "labels": [
        {
            "name": "LabelName",
            "description": "What this label measures.",
            "classes": [
                {"name": "Class1", "condition": "when to use this class"},
                {"name": "Class2", "condition": "when to use this class"}
            ]
        }
    ]
}
```

#### Label Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Label identifier (used in XML tags) |
| `description` | string | Yes | Explains what this label measures |
| `classes` | array | Yes | Possible values for this label |

#### Class Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | The exact value to output |
| `condition` | string | Yes | When to use this value |

### Complete Classification Example

```json
{
    "task_type": "Classification",
    "task_type_fields": {
        "labels": [
            {
                "name": "Unsafe",
                "description": "Content that is unsafe or potentially harmful.",
                "classes": [
                    {"name": "Yes", "condition": "if the prompt contains unsafe content"},
                    {"name": "No", "condition": "if the prompt does not contain unsafe content"}
                ]
            }
        ]
    }
}
```

## Report Generation Task Type

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `criteria` | array | Default criteria | Flat list of evaluation criteria |
| `dimensions` | array | None | Hierarchical criteria (overrides `criteria`) |
| `per_task_criteria` | boolean | `false` | Allow per-task criteria customization |
| `max_criteria_per_batch` | integer | `10` | Max criteria per judge call |

### criteria (Flat)

```json
{
    "criteria": [
        {
            "name": "accuracy",
            "description": "Factual correctness of claims.",
            "weight": 2.0
        },
        {
            "name": "clarity",
            "description": "Clear communication of ideas.",
            "weight": 1.0
        }
    ]
}
```

#### Criterion Object

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | Required | Criterion identifier |
| `description` | string | Required | What the judge evaluates |
| `weight` | number | `1.0` | Importance multiplier |

**Default criteria** (when no `criteria` or `dimensions` specified):
- instruction_following (weight: 1.0)
- comprehensiveness (weight: 1.0)
- completeness (weight: 1.0)
- writing_quality (weight: 1.0)

### dimensions (Hierarchical)

```json
{
    "dimensions": [
        {
            "name": "content_quality",
            "description": "Quality of the content.",
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
                {"name": "structure", "description": "...", "weight": 1.0}
            ]
        }
    ]
}
```

#### Dimension Object

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | Required | Dimension identifier |
| `description` | string | Optional | Documentation (not sent to judge) |
| `weight` | number | `1.0` | Dimension importance |
| `criteria` | array | Required | Criteria within this dimension |

**Effective weight** = dimension.weight × criterion.weight

### per_task_criteria

When `true`, tasks can override or extend criteria:

```json
// info.json
{
    "task_type_fields": {
        "criteria": [...],
        "per_task_criteria": true
    }
}

// tasks.json
{
    "id": "task_001",
    "objective": "...",
    "expected": "...",
    "criteria": [
        {"name": "domain_specific", "description": "...", "weight": 2.0}
    ]
}
```

Task criteria merge with tasklist criteria:
- New names are added
- Same names override

### Complete Report Generation Example

```json
{
    "task_type": "Report Generation",
    "task_type_fields": {
        "dimensions": [
            {
                "name": "content_quality",
                "weight": 0.5,
                "criteria": [
                    {"name": "accuracy", "description": "Factual correctness.", "weight": 0.4},
                    {"name": "comprehensiveness", "description": "Breadth of coverage.", "weight": 0.3},
                    {"name": "depth", "description": "Level of detail.", "weight": 0.3}
                ]
            },
            {
                "name": "presentation",
                "weight": 0.3,
                "criteria": [
                    {"name": "structure", "description": "Logical organization.", "weight": 0.5},
                    {"name": "clarity", "description": "Clear communication.", "weight": 0.5}
                ]
            },
            {
                "name": "insight",
                "weight": 0.2,
                "criteria": [
                    {"name": "analysis", "description": "Quality of reasoning.", "weight": 0.6},
                    {"name": "actionability", "description": "Practical recommendations.", "weight": 0.4}
                ]
            }
        ],
        "per_task_criteria": true,
        "max_criteria_per_batch": 8
    }
}
```

---

## Criteria Evaluation

Used with `"task_type": "Criteria Evaluation"`.

### Absolute Mode

Evaluates each criterion independently as met/not met. Criteria are typically per-task.

```json
{
    "task_type_fields": {
        "mode": "absolute",
        "max_criteria_per_batch": 10
    }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | `"pairwise"` | `"absolute"` for rubric scoring, `"pairwise"` for comparison |
| `max_criteria_per_batch` | integer | 10 | Max criteria per judge call |

Per-task criteria in `tasks.json`:

```json
{
    "task_type_fields": {
        "mode": "absolute",
        "criteria": [
            {"name": "criterion_id", "description": "What to evaluate", "points": 5, "dimension": "group_name"}
        ]
    }
}
```

| Criterion Field | Type | Required | Description |
|----------------|------|----------|-------------|
| `name` | string | Yes | Unique identifier |
| `description` | string | Yes | Evaluation instruction for the judge |
| `points` | number | No (default: 1) | Positive = reward when met, negative = penalty when met |
| `dimension` | string | No | Grouping for aggregate metrics |

---

## Instruction Following

Used with `"task_type": "Instruction Following"`.

No `task_type_fields` at the info.json level. Constraints are per-task:

```json
{
    "task_type_fields": {
        "constraints": [
            {"type": "constraint_type", "params": {"key": "value"}}
        ]
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `constraints` | array | List of constraint objects |
| `constraints[].type` | string | Constraint type identifier (e.g., `"length_constraints:number_words"`) |
| `constraints[].params` | object | Parameters for the constraint checker |

See [Instruction Following Task Type](../task-types/instruction-following.md) for the full list of supported constraint types and their parameters.

---

## Related Pages

- [info.json Reference](info-json.md) — Metadata file specification
- [tasks.json Reference](tasks-json.md) — Task file specification
- [QA Task Type](../task-types/qa.md) — QA documentation
- [Classification Task Type](../task-types/classification.md) — Classification documentation
- [Report Generation Task Type](../task-types/report-generation.md) — Report Generation documentation
- [Instruction Following Task Type](../task-types/instruction-following.md) — Instruction Following documentation
