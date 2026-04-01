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

The `metrics` object is organized into three sections: run-level counters at the top, task-type-specific metrics under `task_type`, and agent execution metrics under `agent`.

```json
{
    "task_count": 10,
    "evaluated_count": 9,
    "correct_count": 7,
    "skipped_count": 1,
    "total_time": 45.2,
    "accuracy": 0.778,
    "task_type": { },
    "agent": { }
}
```

### Run-Level Metrics

Always present regardless of task type.

| Field | Type | Description |
|-------|------|-------------|
| `task_count` | int | Total number of tasks (including skipped) |
| `evaluated_count` | int | Tasks that received a real answer from the agent |
| `correct_count` | int | Tasks that passed verification |
| `skipped_count` | int | Tasks excluded from accuracy due to infrastructure failures |
| `total_time` | float | Total evaluation time in seconds |
| `accuracy` | float | `correct_count / evaluated_count` (0.0 to 1.0). Skipped tasks are excluded from the denominator. |

### Task-Type Metrics (`task_type`)

Computed by the task type's `aggregate()` method. Content varies by task type. All task-type-specific metrics are nested under the `task_type` key.

#### QA

QA tasklists produce no additional task-type metrics beyond accuracy. The `task_type` object is empty.

```json
"task_type": {}
```

#### Classification

Present when evaluating Classification tasklists (e.g., GuardBench, ValuesEval24, Sycophancy-Binary).

| Field | Type | Description |
|-------|------|-------------|
| `task_type.per_label.<name>.precision` | float | Precision for this label |
| `task_type.per_label.<name>.recall` | float | Recall for this label |
| `task_type.per_label.<name>.f1` | float | F1 score for this label |
| `task_type.per_label.<name>.fpr` | float | False positive rate |
| `task_type.per_label.<name>.fnr` | float | False negative rate |
| `task_type.per_label.<name>.confusion` | object | `{tp, fp, tn, fn}` counts |
| `task_type.macro.precision` | float | Macro-averaged precision across labels |
| `task_type.macro.recall` | float | Macro-averaged recall across labels |
| `task_type.macro.f1` | float | Macro-averaged F1 across labels |
| `task_type.macro.fpr` | float | Macro-averaged false positive rate |
| `task_type.macro.fnr` | float | Macro-averaged false negative rate |
| `task_type.micro.precision` | float | Micro-averaged precision |
| `task_type.micro.recall` | float | Micro-averaged recall |
| `task_type.micro.f1` | float | Micro-averaged F1 |
| `task_type.micro.fpr` | float | Micro-averaged false positive rate |
| `task_type.micro.fnr` | float | Micro-averaged false negative rate |

The **positive class** for each label is the first class listed in the label's `classes` configuration.

For binary tasklists (1 label, 2 classes), macro and micro averages are identical to the per-label metrics.

#### Report Generation

Present when evaluating Report Generation tasklists (e.g., DeepConsult, DeepResearchBench).

| Field | Type | Description |
|-------|------|-------------|
| `task_type.avg_normalized_score` | float | Average normalized pairwise comparison score (0=worst, 0.5=tie, 1=best) |
| `task_type.per_dimension_avg.<name>` | float | Average gap score per dimension (if hierarchical criteria used) |
| `task_type.per_criteria_avg.<name>` | float | Average gap score per criterion |

### Agent Execution Metrics (`agent`)

Present when the agent produces execution statistics (agentic paradigms with tools). These metrics are nested under the `agent` key.

For `OpenAIAPIAgent` and `MCPAgent`, the `agent` object is empty (no execution stats available).

| Field | Type | Description |
|-------|------|-------------|
| `agent.pass@{k}s` | float | Fraction of tasks passed within k steps (k = 1, 3, 6, 10) |
| `agent.pass@{k}tc` | float | Fraction of tasks passed within k tool calls (k = 1, 3, 6, 10) |
| `agent.avg_n_steps` | float | Average steps per task |
| `agent.avg_n_steps_passed` | float | Average steps for passed tasks |
| `agent.avg_n_steps_failed` | float | Average steps for failed tasks |
| `agent.avg_n_toolcalls` | float | Average tool calls per task |
| `agent.avg_n_toolcalls_passed` | float | Average tool calls for passed tasks |
| `agent.avg_n_toolcalls_failed` | float | Average tool calls for failed tasks |
| `agent.tool_hallucination_rate` | float | Fraction of tool calls that targeted non-existent tools |

## Per-Task Fields (`detailed_report`)

Each task in `detailed_report` contains:

| Field | Type | Description |
|-------|------|-------------|
| `objective` | string | The prompt sent to the model |
| `expected` | string\|null | Expected output (format varies by task type) |
| `actual` | string\|null | Raw model response. `null` if the agent did not respond. |
| `is_correct` | boolean | Whether the task passed verification. Always `false` for skipped tasks. |
| `is_skipped` | boolean | Whether the task was excluded from metrics due to an infrastructure failure. Always present. |
| `skip_reason` | string\|null | Machine-readable reason for skipping. `null` for non-skipped tasks. Always present. |
| `reasoning` | string\|null | Judge or verification explanation. `null` for skipped tasks. |
| `elapsed_time` | float | Time taken for this task in seconds |
| `metrics` | object | Task-type-specific per-task metrics (optional) |

### Skip Reasons

When `is_skipped` is `true`, `skip_reason` contains one of these values:

| Value | Description |
|-------|-------------|
| `no_response` | The agent did not produce a response. This includes convergence failures (max steps reached without a final answer), API timeouts after all retries, and connection errors. |
| `agent_error` | The agent raised an unexpected exception during execution. |
| `verification_error` | The verification pipeline failed — for example, the judge could not parse its own output after multiple retries, or returned an invalid judgement value. |
| `unsupported_attachment` | The task has an attachment that is neither text nor a recognized image format. |
| `custom_verificator_error` | The task's custom verification function raised an exception. |

### Per-Task Metrics by Task Type

**Classification**: `metrics.per_label.<name>` with `predicted`, `expected`, `correct`, `positive_class`.

**Report Generation**: `metrics.normalized_score`, `metrics.criteria_scores`, `metrics.dimension_scores`.

**QA**: `metrics.criterion` (name of the correctness criterion used).

## Examples

### QA (SimpleQA)

```json
{
    "agent": "gpt-4o",
    "tasklist": "SimpleQA",
    "accuracy": 0.9,
    "metrics": {
        "task_count": 10,
        "evaluated_count": 10,
        "correct_count": 9,
        "skipped_count": 0,
        "total_time": 15.3,
        "accuracy": 0.9,
        "task_type": {},
        "agent": {}
    }
}
```

### Classification (GuardBench)

```json
{
    "agent": "gpt-4o",
    "tasklist": "GuardBench-EN",
    "accuracy": 0.85,
    "metrics": {
        "task_count": 20,
        "evaluated_count": 20,
        "correct_count": 17,
        "skipped_count": 0,
        "total_time": 30.5,
        "accuracy": 0.85,
        "task_type": {
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
        },
        "agent": {}
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
        "evaluated_count": 5,
        "correct_count": 5,
        "skipped_count": 0,
        "total_time": 250.3,
        "accuracy": 1.0,
        "task_type": {
            "avg_normalized_score": 0.72,
            "per_dimension_avg": {"content_quality": 0.8, "writing": 0.65},
            "per_criteria_avg": {"instruction_following": 3.2, "comprehensiveness": 1.5}
        },
        "agent": {}
    }
}
```

### Run with Skipped Tasks

```json
{
    "agent": "gpt-4o",
    "tasklist": "GAIA",
    "accuracy": 0.75,
    "metrics": {
        "task_count": 10,
        "evaluated_count": 8,
        "correct_count": 6,
        "skipped_count": 2,
        "total_time": 120.5,
        "accuracy": 0.75,
        "task_type": {},
        "agent": {}
    },
    "detailed_report": {
        "task_001": {
            "objective": "What is the capital of France?",
            "expected": "Paris",
            "actual": "Paris",
            "is_correct": true,
            "is_skipped": false,
            "skip_reason": null,
            "reasoning": "The answer matches the reference.",
            "elapsed_time": 2.3
        },
        "task_002": {
            "objective": "Solve this complex problem...",
            "expected": "42",
            "actual": null,
            "is_correct": false,
            "is_skipped": true,
            "skip_reason": "no_response",
            "reasoning": null,
            "elapsed_time": 45.0
        }
    }
}
```

## Code Examples

### Overall Accuracy

```python
import json

with open("results/eval.jsonl") as f:
    results = [json.loads(line) for line in f]

for run in results:
    m = run["metrics"]
    print(f"{run['tasklist']}: {run['accuracy']:.1%} ({m['skipped_count']} skipped)")
```

### Classification Metrics

```python
import json

with open("results/eval.jsonl") as f:
    results = [json.loads(line) for line in f]

for run in results:
    tt = run["metrics"].get("task_type", {})
    if "per_label" in tt:
        print(f"{run['tasklist']}:")
        for label, m in tt["per_label"].items():
            print(f"  {label}: F1={m['f1']:.3f} P={m['precision']:.3f} R={m['recall']:.3f}")
        print(f"  Macro F1: {tt['macro']['f1']:.3f}")
```

### Find Failures

```python
import json

with open("results/eval.jsonl") as f:
    results = [json.loads(line) for line in f]

for run in results:
    for task_id, task in run["detailed_report"].items():
        if not task["is_correct"] and not task["is_skipped"]:
            print(f"INCORRECT: {task_id}")
            print(f"  Expected: {task['expected']}")
            print(f"  Got: {task['actual'][:100]}")
```

### Find Skipped Tasks

```python
import json

with open("results/eval.jsonl") as f:
    results = [json.loads(line) for line in f]

for run in results:
    for task_id, task in run["detailed_report"].items():
        if task["is_skipped"]:
            print(f"SKIPPED: {task_id} — {task['skip_reason']}")
```
