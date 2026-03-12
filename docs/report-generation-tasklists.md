# Creating Report Generation Tasklists

This guide explains how to create and customize report generation tasklists for evaluation with palace.

## What is Report Generation?

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
    "score_provided": 12.0,
    "score_expected": 3.5
  }
}
```

- `criteria_scores`: Per-criterion score (-10 to +10, positive = generated better)
- `overall_gap`: Weighted sum of criteria scores
- `is_correct`: True if `score_provided > score_expected`
