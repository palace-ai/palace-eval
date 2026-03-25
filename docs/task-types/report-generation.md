# Report Generation Task Type

Evaluate long-form content through pairwise comparison with weighted criteria.

!!! tip "When to Use"
    Use Report Generation when evaluating documents, reports, summaries, or any long-form content where multiple quality dimensions matter.

## Overview

Report generation tasks evaluate a model's ability to produce long-form, structured documents in response to a prompt. Unlike QA tasks with short factual answers, report generation assesses complex writing abilities: research synthesis, logical organization, depth of analysis, and clear communication.

## How Evaluation Works

Palace uses **pairwise comparison** with an LLM judge:

1. The model generates a report from a prompt
2. A judge LLM compares the generated report against a reference report
3. For each **criterion** (evaluation dimension), the judge decides which report is better and by how much
4. To reduce position bias, the comparison runs twice with reports swapped
5. Scores are aggregated across criteria (with optional weights)
6. The task passes if the generated report outscores the reference

**Criteria** are the dimensions you care about—instruction following, technical accuracy, writing quality, etc. You define what matters for your use case.

## Tasklist Structure

A report generation tasklist requires two files in `~/.cache/palace/tasklists/{TasklistName}/`:

```
{TasklistName}/
├── info.json      # Tasklist metadata and evaluation config
└── tasks.json     # List of tasks (prompts + reference reports)
```

## Basic Example

### info.json

```json
{
  "name": "MyReportBench",
  "id": "my-org/MyReportBench",
  "original": true,
  "category": "Report Generation",
  "task_type": "Report Generation"
}
```

With no `task_type_fields`, the default criteria are used:
- instruction_following
- comprehensiveness
- completeness
- writing_quality

### tasks.json

```json
[
  {
    "id": "task_001",
    "objective": "Write a report analyzing the impact of remote work on productivity.",
    "expected": "# Remote Work and Productivity\n\n## Introduction\n\nThe shift to remote work..."
  },
  {
    "id": "task_002", 
    "objective": "Create a technical report on renewable energy adoption in Europe.",
    "expected": "# Renewable Energy in Europe\n\n## Executive Summary\n\n..."
  }
]
```

Each task needs:
- `id`: Unique identifier
- `objective`: The prompt given to the model
- `expected`: Reference report for comparison

## Custom Criteria

Define your own evaluation criteria in `info.json`:

```json
{
  "name": "TechReportBench",
  "id": "my-org/TechReportBench",
  "original": true,
  "category": "Report Generation",
  "task_type": "Report Generation",
  "task_type_fields": {
    "criteria": [
      {
        "name": "technical_accuracy",
        "description": "Correctness of technical claims, proper use of terminology, and accuracy of data presented.",
        "weight": 2.0
      },
      {
        "name": "structure",
        "description": "Logical organization with clear sections, appropriate headings, and smooth transitions.",
        "weight": 1.0
      },
      {
        "name": "actionability",
        "description": "Provides concrete recommendations that readers can implement.",
        "weight": 1.5
      }
    ]
  }
}
```

### Criteria Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Identifier (snake_case recommended) |
| `description` | Yes | What the judge evaluates - be specific |
| `weight` | No | Importance multiplier (default: 1.0) |

### Weight Example

With weights `[2.0, 1.0, 1.5]`:
- technical_accuracy contributes 2x to the final score
- structure contributes 1x
- actionability contributes 1.5x

## Per-Task Criteria

For tasklists where different tasks need different evaluation criteria, enable per-task customization:

### info.json

```json
{
  "name": "MixedReportBench",
  "original": true,
  "task_type": "Report Generation",
  "task_type_fields": {
    "criteria": [
      {"name": "clarity", "description": "Clear and understandable writing.", "weight": 1.0},
      {"name": "completeness", "description": "Covers all required topics.", "weight": 1.0}
    ],
    "per_task_criteria": true
  }
}
```

### tasks.json

```json
[
  {
    "id": "financial_report",
    "objective": "Write a quarterly financial analysis...",
    "expected": "...",
    "criteria": [
      {
        "name": "numerical_accuracy",
        "description": "All numbers, percentages, and calculations are correct.",
        "weight": 3.0
      }
    ]
  },
  {
    "id": "narrative_report",
    "objective": "Write a company history report...",
    "expected": "...",
    "criteria": [
      {
        "name": "storytelling",
        "description": "Engaging narrative that maintains reader interest.",
        "weight": 2.0
      }
    ]
  }
]
```

### Merge Behavior

When `per_task_criteria: true`:
- Task criteria **add** to tasklist criteria (new names)
- Task criteria **override** tasklist criteria (same name)

In the example above:
- `financial_report` is evaluated on: clarity, completeness, numerical_accuracy
- `narrative_report` is evaluated on: clarity, completeness, storytelling

## Evaluation Flow

1. Model receives `objective` as prompt
2. Model generates a report
3. LLM judge compares generated report vs `expected` report
4. For each criterion:
   - Judge scores which report is better (A or B)
   - Judge assigns gap score (0-5)
5. Comparison runs twice (A/B then B/A) to reduce position bias
6. Weighted scores aggregated
7. Task passes if generated report scores higher than reference

## Writing Good Criteria

### Be Specific

❌ Bad: `"quality": "How good the report is."`

✅ Good: `"evidence_quality": "Claims are supported by specific data, citations, or concrete examples rather than vague assertions."`

### Match Your Domain

For **technical reports**:
```json
{"name": "technical_depth", "description": "Demonstrates deep understanding of the subject with appropriate technical detail."}
```

For **executive summaries**:
```json
{"name": "conciseness", "description": "Conveys key points efficiently without unnecessary detail or repetition."}
```

For **research reports**:
```json
{"name": "methodology_clarity", "description": "Research approach is clearly explained and justified."}
```

### Balance Weights

- Use higher weights (1.5-3.0) for criteria critical to your use case
- Use lower weights (0.5-1.0) for nice-to-have qualities
- Default weight is 1.0

## Running Evaluation

```python
from palace import evaluate

evaluate(
    model_url="https://api.example.com/v1",
    model_token="your-token",
    tasklist="MyReportBench",
    output_path="./results"
)
```

Or via CLI:
```bash
palace-run --tasklist MyReportBench --model-url https://api.example.com/v1
```

## Output Metrics

The evaluation returns per-task metrics:

```json
{
  "is_correct": true,
  "metrics": {
    "criteria_scores": {
      "technical_accuracy": 4,
      "structure": -1,
      "actionability": 2
    },
    "overall_gap": 8.5,
    "normalized_score": 0.59,
    "score_provided": 12.0,
    "score_expected": 3.5
  }
}
```

- `criteria_scores`: Per-criterion score (-10 to +10, positive = generated better)
- `overall_gap`: Weighted sum of criteria scores
- `normalized_score`: Gap rescaled to [0, 1] where 0.5 = tie, 1.0 = max win
- `is_correct`: True if `score_provided > score_expected`

## Aggregate Metrics

After all tasks are evaluated, PALACE computes aggregate report generation metrics:

| Metric | Description |
|--------|-------------|
| `avg_normalized_score` | Average normalized score across all tasks (0=worst, 0.5=tie, 1=best) |
| `per_criteria_avg` | Average gap score per criterion across all tasks |
| `per_dimension_avg` | Average gap score per dimension (if hierarchical criteria used) |

These appear in the top-level `metrics` object of the JSONL output alongside universal metrics like `task_count` and `accuracy`.

## Hierarchical Criteria (Dimensions)

For complex benchmarks with many criteria, group them into weighted dimensions:

### info.json

```json
{
  "name": "DeepResearchBench",
  "original": true,
  "task_type": "Report Generation",
  "task_type_fields": {
    "dimensions": [
      {
        "name": "comprehensiveness",
        "description": "Measures breadth and depth of coverage.",
        "weight": 0.3,
        "criteria": [
          {"name": "topic_coverage", "description": "Covers all required topics.", "weight": 0.5},
          {"name": "detail_depth", "description": "Sufficient detail on each topic.", "weight": 0.5}
        ]
      },
      {
        "name": "insight",
        "description": "Quality of analysis and conclusions.",
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

### Dimension Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Dimension identifier |
| `description` | No | Documentation (not sent to judge) |
| `weight` | No | Dimension importance (default: 1.0) |
| `criteria` | Yes | List of criteria within this dimension |

### Weight Calculation

Effective weight = `dimension.weight × criterion.weight`

In the example above:
- `topic_coverage`: 0.3 × 0.5 = 0.15
- `detail_depth`: 0.3 × 0.5 = 0.15
- `analysis_quality`: 0.7 × 0.6 = 0.42
- `conclusions`: 0.7 × 0.4 = 0.28

### Dimension Metrics

When using hierarchical criteria, output includes `dimension_scores`:

```json
{
  "metrics": {
    "criteria_scores": {"topic_coverage": 3, "detail_depth": 2, "analysis_quality": 4, "conclusions": 1},
    "dimension_scores": {"comprehensiveness": 5, "insight": 5},
    "overall_gap": 10.0,
    "normalized_score": 0.75
  }
}
```

### Per-Task Dimensions

With `per_task_criteria: true`, tasks can provide their own dimensions via `task_type_fields`:

```json
{
  "id": "specialized_task",
  "objective": "...",
  "expected": "...",
  "task_type_fields": {
    "dimensions": [
      {
        "name": "domain_expertise",
        "weight": 0.5,
        "criteria": [{"name": "accuracy", "description": "Domain-specific accuracy.", "weight": 1.0}]
      }
    ]
  }
}
```

Task `task_type_fields` merge with tasklist `task_type_fields` (task values override on conflict).

## Batched Evaluation

When evaluating many criteria, the judge LLM processes them in batches to maintain accuracy. By default, criteria are grouped by dimension and evaluated up to 10 at a time.

### Configuring Batch Size

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

### Batching Behavior

1. Criteria are grouped by dimension (keeps related criteria together)
2. If a dimension has more criteria than `max_criteria_per_batch`, it's split into sub-batches
3. Flat criteria (no dimensions) are batched sequentially
4. Results from all batches are merged before scoring

This ensures accurate evaluation even with 25+ criteria across multiple dimensions.


---

## Related Pages

- [Choosing a Task Type](index.md) - Compare all task types
- [QA Task Type](qa.md) - For factual question-answering
- [Classification Task Type](classification.md) - For categorical outputs
- [Research Reports Example](../examples/research-reports.md) - DeepResearchBench-style example
- [Task Type Fields Reference](../reference/task-type-fields.md) - Complete field specification
