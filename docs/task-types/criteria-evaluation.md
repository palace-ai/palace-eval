# Criteria Evaluation Task Type

Evaluate model outputs against weighted criteria using an LLM judge. Supports two modes: **pairwise** (compare against a reference) and **absolute** (rubric scoring without a reference).

!!! tip "When to Use"
    Use Criteria Evaluation when evaluating content where multiple quality dimensions matter — research reports, medical responses, summaries, or any output assessed against a rubric.

## Overview

Criteria Evaluation assesses model outputs across multiple configurable criteria. Each criterion has a description (shown to the LLM judge) and a weight (importance multiplier).

**Two modes:**

- **Pairwise** — Compares model output against a reference document. Judge decides which is better per criterion.
- **Absolute** — Evaluates model output against a rubric. Judge scores each criterion independently as met/not met.

## Pairwise Mode

Pairwise mode compares the model's output against a reference document across criteria.

### How It Works

1. The model generates output from a prompt
2. A judge LLM compares the generated output against a reference
3. For each criterion, the judge decides which is better and by how much (gap 0-5)
4. The comparison runs twice with positions swapped (reduces position bias)
5. Scores are aggregated across criteria with weights
6. The task passes if the generated output outscores the reference

### Configuration

```json
{
    "task_type": "Criteria Evaluation",
    "task_type_fields": {
        "criteria": [
            {
                "name": "technical_accuracy",
                "description": "Correctness of technical claims, proper use of terminology, and accuracy of data presented.",
                "weight": 2.0
            },
            {
                "name": "completeness",
                "description": "Covers all required topics with sufficient depth.",
                "weight": 1.0
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

### tasks.json (Pairwise)

Each task needs an `objective` (prompt) and `expected` (reference):

```json
{
    "id": "task_001",
    "objective": "Write a report analyzing the impact of remote work on productivity.",
    "expected": "# Remote Work and Productivity\n\n## Introduction\n\nThe shift to remote work..."
}
```

### Default Criteria

With no `task_type_fields`, these defaults are used:
- instruction_following (weight: 1.0)
- comprehensiveness (weight: 1.0)
- completeness (weight: 1.0)
- writing_quality (weight: 1.0)

### Pairwise Metrics

**Per-task:**

| Metric | Description |
|--------|-------------|
| `criteria_scores` | Per-criterion score (-10 to +10, positive = generated better) |
| `overall_gap` | Weighted sum of criteria scores |
| `normalized_score` | Gap rescaled to [0, 1] where 0.5 = tie, 1.0 = max win |

**Aggregate:**

| Metric | Description |
|--------|-------------|
| `avg_normalized_score` | Average normalized score across all tasks |
| `per_criteria_avg` | Average gap score per criterion |
| `per_dimension_avg` | Average per dimension (if hierarchical) |

---

## Absolute Mode

Absolute mode evaluates responses against a rubric without a reference document. Each criterion is independently judged as met or not met.

### When to Use

- No reference document available
- Each criterion is independently assessable (YES/NO)
- Criteria have different point values
- You want penalty scoring (negative points for bad behaviors)

### Configuration

**info.json:**

```json
{
    "name": "MyRubricBench",
    "task_type": "Criteria Evaluation",
    "task_type_fields": {
        "mode": "absolute"
    }
}
```

**tasks.json** — criteria are per-task:

```json
{
    "id": "health_001",
    "objective": "I have a headache and fever. What should I do?",
    "expected": "",
    "task_type_fields": {
        "mode": "absolute",
        "criteria": [
            {"name": "recommends_rest", "description": "Recommends rest and hydration", "points": 5, "dimension": "completeness"},
            {"name": "suggests_doctor", "description": "Suggests seeing a doctor if symptoms persist", "points": 3, "dimension": "accuracy"},
            {"name": "no_diagnosis", "description": "Does not provide a specific diagnosis", "points": -5, "dimension": "accuracy"}
        ]
    }
}
```

### Scoring

- **Positive points**: Earned when criterion IS met (good behavior)
- **Negative points**: Penalty applied when criterion IS met (bad behavior detected)
- **Score** = earned_points / max_positive_points, clamped to [0, 1]
- **Task passes** if score ≥ 0.5

### Criteria Fields (Absolute)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique identifier |
| `description` | string | Yes | What the judge evaluates (shown to LLM) |
| `points` | number | No (default: 1) | Positive = reward when met, negative = penalty when met |
| `dimension` | string | No | Grouping for metrics aggregation |

### Absolute Metrics

**Per-task:**

| Metric | Description |
|--------|-------------|
| `normalized_score` | Score for this task (0.0 to 1.0) |
| `earned_points` | Total points earned |
| `max_points` | Maximum possible positive points |
| `dimension_scores` | Satisfaction rate per dimension |

**Aggregate:**

| Metric | Description |
|--------|-------------|
| `accuracy` | Fraction of tasks with score ≥ 0.5 |
| `avg_normalized_score` | Average score across all tasks |
| `per_dimension_avg` | Average satisfaction rate per dimension |
| `per_criteria_avg` | Average satisfaction rate per criterion |

### Example Output

```
✓ recommends_rest (+5pts): Recommends rest and hydration
✓ suggests_doctor (+3pts): Suggests seeing a doctor if symptoms persist
✗ no_diagnosis (-5pts): Does not provide a specific diagnosis

Score: 8.0/8.0 = 1.00
```

---

## Hierarchical Criteria (Dimensions)

For complex benchmarks with many criteria, group them into weighted dimensions. Works with both pairwise and absolute modes.

### Configuration

```json
{
    "task_type": "Criteria Evaluation",
    "task_type_fields": {
        "dimensions": [
            {
                "name": "comprehensiveness",
                "weight": 0.3,
                "criteria": [
                    {"name": "topic_coverage", "description": "Covers all required topics.", "weight": 0.5},
                    {"name": "detail_depth", "description": "Sufficient detail on each topic.", "weight": 0.5}
                ]
            },
            {
                "name": "insight",
                "weight": 0.7,
                "criteria": [
                    {"name": "analysis_quality", "description": "Sound reasoning and analysis.", "weight": 0.6},
                    {"name": "conclusions", "description": "Actionable, well-supported conclusions.", "weight": 0.4}
                ]
            }
        ]
    }
}
```

### Weight Calculation

Effective weight = `dimension.weight × criterion.weight`

In the example above:
- `topic_coverage`: 0.3 × 0.5 = 0.15
- `detail_depth`: 0.3 × 0.5 = 0.15
- `analysis_quality`: 0.7 × 0.6 = 0.42
- `conclusions`: 0.7 × 0.4 = 0.28

### Dimension Metrics

Output includes `dimension_scores` (average of criteria in each dimension) and `criteria_scores` nested by dimension:

```json
{
    "metrics": {
        "criteria_scores": {
            "comprehensiveness": {"topic_coverage": 3, "detail_depth": 2},
            "insight": {"analysis_quality": 4, "conclusions": 1}
        },
        "dimension_scores": {"comprehensiveness": 2.5, "insight": 2.5}
    }
}
```

---

## Per-Task Criteria

Enable task-specific criteria that merge with tasklist-level criteria:

**info.json:**

```json
{
    "task_type_fields": {
        "criteria": [...],
        "per_task_criteria": true
    }
}
```

**tasks.json:**

```json
{
    "id": "financial_report",
    "objective": "Write a quarterly financial analysis...",
    "expected": "...",
    "criteria": [
        {"name": "numerical_accuracy", "description": "All numbers are correct.", "weight": 3.0}
    ]
}
```

Merge behavior:
- New names are **added** to tasklist criteria
- Same names **override** tasklist criteria

---

## Batched Evaluation

When evaluating many criteria, the judge processes them in batches for accuracy.

```json
{
    "task_type_fields": {
        "max_criteria_per_batch": 8,
        "dimensions": [...]
    }
}
```

| Field | Default | Description |
|-------|---------|-------------|
| `max_criteria_per_batch` | 10 | Maximum criteria per judge call |

Criteria are grouped by dimension. If a dimension exceeds the batch size, it's split into sub-batches.

---

## Writing Good Criteria

### Be Specific

❌ `"quality": "How good the report is."`

✅ `"evidence_quality": "Claims are supported by specific data, citations, or concrete examples rather than vague assertions."`

### Balance Weights

- **High (2.0-3.0)**: Critical requirements
- **Normal (1.0)**: Standard importance
- **Low (0.5)**: Nice-to-have qualities

---

## Running Evaluation

```python
from palace import evaluate

evaluate(
    run_name="criteria-eval",
    output_folder="./results",
    url="https://api.example.com/v1",
    token="your-token",
    name="gpt-4o",
    tasklist="MyBench",
)
```

Or via CLI:
```bash
palace run MyBench -m gpt-4o
```

---

## Related Pages

- [Choosing a Task Type](index.md)
- [QA Task Type](qa.md)
- [Classification Task Type](classification.md)
- [Instruction Following Task Type](instruction-following.md)
- [Custom Criteria Guide](../howto/custom-criteria.md)
- [Task Type Fields Reference](../reference/task-type-fields.md)
