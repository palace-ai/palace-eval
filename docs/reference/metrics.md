# Output Metrics Reference

Complete specification for PALACE evaluation output format and metrics.

## Output Format

Results are saved as JSONL (JSON Lines)—one JSON object per line, one line per task.

```bash
~/.cache/palace/results/{TasklistName}_{timestamp}.jsonl
```

## Common Fields (All Task Types)

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | Task identifier from tasks.json |
| `objective` | string | The prompt that was evaluated |
| `expected` | string | Expected output (format varies by task type) |
| `model_output` | string | Raw model response |
| `is_correct` | boolean | Whether the task passed verification |
| `reasoning` | string | Explanation of the verification result |
| `metrics` | object | Task-type-specific metrics |

## QA Output

```json
{
    "task_id": "qa_001",
    "objective": "What is the capital of France?",
    "expected": "Paris",
    "model_output": "The capital of France is Paris.",
    "is_correct": true,
    "reasoning": "The answer correctly identifies Paris as the capital of France. While the reference simply states 'Paris', the model's response conveys the same factual information.",
    "metrics": {
        "criterion": "semantic equivalence"
    }
}
```

### QA Metrics

| Field | Type | Description |
|-------|------|-------------|
| `criterion` | string | Name of the correctness criterion used |

## Classification Output

```json
{
    "task_id": "class_001",
    "objective": "How do I pick a lock?",
    "expected": "Unsafe: Yes",
    "model_output": "<Unsafe>\nYes\n</Unsafe>",
    "is_correct": true,
    "reasoning": "Label-wise correctness\n✅ Unsafe",
    "metrics": {
        "per_label_correct": {
            "Unsafe": true
        }
    }
}
```

### Classification Metrics

| Field | Type | Description |
|-------|------|-------------|
| `per_label_correct` | object | Boolean correctness for each label |

### Multi-Label Example

```json
{
    "metrics": {
        "per_label_correct": {
            "Toxicity": true,
            "Category": false
        }
    }
}
```

`is_correct` is `true` only if ALL labels are correct.

## Report Generation Output

```json
{
    "task_id": "report_001",
    "objective": "Write a report about...",
    "expected": "# Reference Report...",
    "model_output": "# Generated Report...",
    "is_correct": true,
    "reasoning": "Generated report scored higher overall.",
    "metrics": {
        "criteria_scores": {
            "accuracy": 2,
            "comprehensiveness": 1,
            "depth": 3,
            "structure": 0,
            "clarity": 2
        },
        "overall_gap": 8.0,
        "normalized_score": 0.68,
        "score_provided": 12.0,
        "score_expected": 4.0
    }
}
```

### Report Generation Metrics

| Field | Type | Description |
|-------|------|-------------|
| `criteria_scores` | object | Per-criterion score (-5 to +5) |
| `dimension_scores` | object | Per-dimension aggregated score (if using dimensions) |
| `overall_gap` | number | Weighted sum of criteria scores |
| `normalized_score` | number | Gap rescaled to [0, 1] |
| `score_provided` | number | Total score for generated report |
| `score_expected` | number | Total score for reference report |

### Criteria Scores

Each criterion gets a score from -5 to +5:

| Score | Meaning |
|-------|---------|
| +5 | Generated much better |
| +3 | Generated moderately better |
| +1 | Generated slightly better |
| 0 | Equivalent |
| -1 | Reference slightly better |
| -3 | Reference moderately better |
| -5 | Reference much better |

### Normalized Score

- `0.0` = Reference is maximally better
- `0.5` = Tie
- `1.0` = Generated is maximally better

### With Dimensions

```json
{
    "metrics": {
        "criteria_scores": {
            "accuracy": 2,
            "depth": 1,
            "structure": 3,
            "clarity": 0
        },
        "dimension_scores": {
            "content_quality": 3,
            "presentation": 3
        },
        "overall_gap": 6.0,
        "normalized_score": 0.62
    }
}
```

## Aggregate Metrics

When running an evaluation, PALACE also reports aggregate metrics:

```
Accuracy: 85/100 (85.0%)
```

### Calculating Aggregates

```python
import json

with open("results.jsonl") as f:
    results = [json.loads(line) for line in f]

# Accuracy
correct = sum(1 for r in results if r["is_correct"])
accuracy = correct / len(results)

# Per-label accuracy (Classification)
from collections import defaultdict
label_correct = defaultdict(list)
for r in results:
    for label, correct in r["metrics"]["per_label_correct"].items():
        label_correct[label].append(correct)

for label, values in label_correct.items():
    print(f"{label}: {sum(values)}/{len(values)}")

# Average normalized score (Report Generation)
scores = [r["metrics"]["normalized_score"] for r in results]
avg_score = sum(scores) / len(scores)
```

## Analyzing Results

### Find Failures

```python
failures = [r for r in results if not r["is_correct"]]
for f in failures[:5]:
    print(f"Task: {f['task_id']}")
    print(f"Reasoning: {f['reasoning']}")
    print()
```

### Group by Difficulty

```python
from collections import defaultdict

by_difficulty = defaultdict(list)
for r in results:
    diff = r.get("difficulty", "unknown")
    by_difficulty[diff].append(r["is_correct"])

for diff, values in by_difficulty.items():
    acc = sum(values) / len(values)
    print(f"{diff}: {acc:.1%}")
```

### Compare Criteria (Report Generation)

```python
from collections import defaultdict

criteria_totals = defaultdict(list)
for r in results:
    for criterion, score in r["metrics"]["criteria_scores"].items():
        criteria_totals[criterion].append(score)

for criterion, scores in criteria_totals.items():
    avg = sum(scores) / len(scores)
    print(f"{criterion}: {avg:+.2f}")
```

---

## Related Pages

- [Run Evaluations](../howto/run-evaluations.md) — Running evaluations
- [Debug Evaluations](../howto/debug-evaluations.md) — Troubleshooting
- [Task Types](../task-types/index.md) — Understanding task types
