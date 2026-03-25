# Output Metrics Reference

Complete specification for PALACE evaluation output format and metrics.

## Output Format

Results are saved as JSONL (JSON Lines)—one JSON object per evaluation run.

```bash
~/.cache/palace/results/eval.jsonl
```

Each line represents a complete evaluation run containing all task results.

## Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `agent` | string | Model name used for evaluation |
| `model` | string | Model type description |
| `paradigm` | string | Evaluation paradigm |
| `environment` | string | Environment description |
| `tasklist` | string | Name of the tasklist evaluated |
| `accuracy` | float | Overall accuracy (0.0 to 1.0) |
| `metrics` | object | Aggregated metrics (see below) |
| `detailed_report` | object | Per-task results keyed by task ID |

## Metrics Object

The `metrics` object contains three categories of metrics, merged into a flat dict:

### Universal Metrics

Always present regardless of task type.

| Field | Type | Description |
|-------|------|-------------|
| `task_count` | int | Total number of tasks evaluated |
| `correct_count` | int | Number of tasks passed |
| `total_time` | float | Total evaluation time in seconds |
| `accuracy` | float | Fraction of tasks passed (0.0 to 1.0) |

### Task-Type Metrics

Computed by the task type's `aggregate()` method. Content varies by task type.

#### Classification Metrics

Present when evaluating Classification tasklists (e.g., GuardBench, ValuesEval24).

| Field | Type | Description |
|-------|------|-------------|
| `classification.per_label.<name>.precision` | float | Precision for this label |
| `classification.per_label.<name>.recall` | float | Recall for this label |
| `classification.per_label.<name>.f1` | float | F1 score for this label |
| `classification.per_label.<name>.fpr` | float | False positive rate |
| `classification.per_label.<name>.fnr` | float | False negative rate |
| `classification.per_label.<name>.confusion` | object | `{tp, fp, tn, fn}` counts |
| `classification.macro.<metric>` | float | Macro-averaged metric across labels |
| `classification.micro.<metric>` | float | Micro-averaged metric across labels |

The **positive class** for each label is the first class listed in the label's `classes` configuration.

For binary tasklists (1 label, 2 classes), macro and micro averages are identical to the per-label metrics.

#### Report Generation Metrics

Present when evaluating Report Generation tasklists (e.g., DeepConsult, DeepResearchBench).

| Field | Type | Description |
|-------|------|-------------|
| `avg_normalized_score` | float | Average normalized pairwise comparison score (0=worst, 0.5=tie, 1=best) |
| `per_dimension_avg` | object | Average gap score per dimension (if hierarchical criteria used) |
| `per_criteria_avg` | object | Average gap score per criterion |

#### QA Metrics

QA tasklists use the default accuracy metric only. No additional task-type metrics.

### Agent-Execution Metrics

Present when the agent produces execution statistics (agentic paradigms with tools).

| Field | Type | Description |
|-------|------|-------------|
| `pass@{k}{s\|tc}` | float | Fraction of tasks passed within k steps (s) or tool calls (tc) |
| `avg_n_steps` | float | Average steps per task |
| `avg_n_steps_passed` | float | Average steps for passed tasks |
| `avg_n_steps_failed` | float | Average steps for failed tasks |
| `avg_n_toolcalls` | float | Average tool calls per task |
| `avg_n_toolcalls_passed` | float | Average tool calls for passed tasks |
| `avg_n_toolcalls_failed` | float | Average tool calls for failed tasks |
| `tool_hallucination_rate` | float | Fraction of tool calls that were hallucinated |

## Example Output

### Classification (GuardBench)

```json
{
    "agent": "gpt-4o",
    "tasklist": "GuardBench-EN",
    "accuracy": 0.85,
    "metrics": {
        "task_count": 20,
        "correct_count": 17,
        "total_time": 30.5,
        "accuracy": 0.85,
        "classification": {
            "per_label": {
                "Unsafe": {
                    "precision": 0.9,
                    "recall": 0.82,
                    "f1": 0.858,
                    "fpr": 0.1,
                    "fnr": 0.18,
                    "confusion": {"tp": 9, "fp": 1, "tn": 8, "fn": 2}
                }
            },
            "macro": {"precision": 0.9, "recall": 0.82, "f1": 0.858, "fpr": 0.1, "fnr": 0.18},
            "micro": {"precision": 0.9, "recall": 0.82, "f1": 0.858, "fpr": 0.1, "fnr": 0.18}
        }
    }
}
```

### Report Generation (DeepResearchBench)

```json
{
    "agent": "gpt-4o",
    "tasklist": "DeepResearchBench-Test",
    "accuracy": 1.0,
    "metrics": {
        "task_count": 5,
        "correct_count": 5,
        "total_time": 250.3,
        "accuracy": 1.0,
        "avg_normalized_score": 0.72,
        "per_dimension_avg": {"content_quality": 0.8, "writing": 0.65},
        "per_criteria_avg": {"instruction_following": 3.2, "comprehensiveness": 1.5}
    }
}
```

## Per-Task Fields (detailed_report)

Each task in `detailed_report` contains:

| Field | Type | Description |
|-------|------|-------------|
| `objective` | string | The prompt sent to the model |
| `expected` | string | Expected output (format varies by task type) |
| `actual` | string | Raw model response |
| `is_correct` | boolean | Whether the task passed verification |
| `reasoning` | string | Explanation of the verification result |
| `elapsed_time` | float | Time taken for this task in seconds |
| `metrics` | object | Task-type-specific per-task metrics (optional) |

### Per-Task Metrics by Task Type

**Classification**: `metrics.per_label.<name>` with `predicted`, `expected`, `correct`, `positive_class`.

**Report Generation**: `metrics.normalized_score`, `metrics.criteria_scores`, `metrics.dimension_scores`.

**QA**: `metrics.criterion` (name of the correctness criterion used).

## Calculating Aggregates

### Overall Accuracy

```python
import json

with open("results/eval.jsonl") as f:
    results = [json.loads(line) for line in f]

for run in results:
    print(f"{run['tasklist']}: {run['accuracy']:.1%}")
```

### Classification Metrics

```python
import json

with open("results/eval.jsonl") as f:
    results = [json.loads(line) for line in f]

for run in results:
    clf = run["metrics"].get("classification")
    if clf:
        print(f"{run['tasklist']}:")
        for label, m in clf["per_label"].items():
            print(f"  {label}: F1={m['f1']:.3f} P={m['precision']:.3f} R={m['recall']:.3f}")
        print(f"  Macro F1: {clf['macro']['f1']:.3f}")
```

### Find Failures

```python
import json

with open("results/eval.jsonl") as f:
    results = [json.loads(line) for line in f]

for run in results:
    for task_id, task in run["detailed_report"].items():
        if not task["is_correct"]:
            print(f"FAILED: {task_id}")
            print(f"  Expected: {task['expected']}")
            print(f"  Got: {task['actual'][:100]}")
```
