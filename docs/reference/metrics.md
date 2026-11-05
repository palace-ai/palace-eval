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
| `model` | string | Model name |
| `tasklist` | string | Name of the tasklist evaluated |
| `accuracy` | float | Overall accuracy (0.0 to 1.0) |
| `metrics` | object | Aggregated metrics (see below) |
| `detailed_report` | object | Per-task results keyed by task ID. Omitted with `--report-detail=none`. |

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

#### Criteria Evaluation (Pairwise)

Present when evaluating Criteria Evaluation tasklists in pairwise mode (e.g., DeepConsult, DeepResearchBench).

| Field | Type | Description |
|-------|------|-------------|
| `task_type.avg_normalized_score` | float | Average normalized pairwise comparison score (0=worst, 0.5=tie, 1=best) |
| `task_type.per_dimension_avg.<name>` | float | Average gap score per dimension, computed as mean of criteria averages (if hierarchical criteria used) |
| `task_type.per_criteria_avg.<name>` | float | Average gap score per criterion. Nested by dimension for hierarchical tasklists (e.g., `per_criteria_avg.<dim>.<crit>`) |

#### Criteria Evaluation (Absolute Mode)

Present when evaluating Criteria Evaluation tasklists in absolute mode (e.g., HealthBench).

| Field | Type | Description |
|-------|------|-------------|
| `task_type.avg_normalized_score` | float | Average rubric score across all tasks (0.0 to 1.0) |
| `task_type.per_dimension_avg.<name>` | float | Average criterion satisfaction rate per dimension |
| `task_type.per_criteria_avg.<name>` | float | Average satisfaction rate per criterion |

#### Instruction Following

Present when evaluating Instruction Following tasklists (e.g., IFEval).

| Field | Type | Description |
|-------|------|-------------|
| `task_type.avg_score` | float | Average constraint satisfaction score across all tasks |

### Agent Execution Metrics (`agent`)

Present when the agent produces execution statistics (agentic evaluation via Vivarium). These metrics are nested under the `agent` key.

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

Each task in `detailed_report` is keyed by task ID and contains:

| Field | Type | Description |
|-------|------|-------------|
| `actual` | string\|null | Raw model response. `null` if the agent did not respond. |
| `is_correct` | boolean | Whether the task passed verification. Always `false` for skipped tasks. |
| `is_skipped` | boolean | Whether the task was excluded from metrics due to an infrastructure failure. Always present. |
| `skip_reason` | string\|null | Machine-readable reason for skipping. `null` for non-skipped tasks. Always present. |
| `reasoning` | string\|null | Judge or verification explanation. `null` for skipped tasks. |
| `operational` | object | Operational metrics bucket for this task (see below) |
| `metrics` | object | Task-type-specific per-task metrics (optional) |
| `objective` | string | The prompt sent to the model. Only present with `--report-detail=full`. |
| `expected` | string\|null | Expected output. Only present with `--report-detail=full`. |

### Per-Task Operational Metrics (`operational`)

All observability metrics live in a single `operational` bucket, nested by
**metric type**: `timing` (durations), `throughput` (rates), `tokens`
(server-reported counts) and `chunks` (client-observed delivery facts).
`reasoning_status` sits at the bucket root as the regime flag that conditions
every other field. Key sets are identical on **every** endpoint — a value is
`null` when the endpoint does not provide it *or* when the reasoning regime
makes it unreliable, so downstream consumers can rely on a stable JSON shape:

```json
"operational": {
  "reasoning_status": "none",
  "timing": {
    "total_seconds": 1.64,             // client: t0 -> full stream consumption
    "wall_seconds": 1.7,               // whole agent run incl. retries
    "ttfc_seconds": 1.63,              // client: time to first output chunk
    "ttfcc_seconds": 1.63,             // client: time to first *content* chunk
    "server": {                         // server-reported (authoritative)
      "engine_ttft_seconds": 0.567,
      "service_ttft_seconds": 0.786,
      "user_visible_ttft_seconds": 0.667,
      "pre_inference_seconds": 0.118,
      "engine_tbt_seconds": 0.025,
      "service_tbt_seconds": 0.031,
      "engine_ttlt_seconds": 0.693
    }
  },
  "throughput": {
    "prefill_cps": 12.3,               // input tokens / ttfc
    "generation_cps": 30.1,            // output tokens / generation window
    "content_cps": 30.1,               // content tokens / content window
    "total_cps": 14.7                  // (input+output) / full span
  },
  "tokens": {
    "input_tokens": 20,
    "output_tokens": 45,
    "reasoning_tokens": null
  },
  "chunks": { "output_chunks": 1, "reasoning_chunks": 0 }
}
```

**Vocabulary**: *prefill = input*, *generation = output = reasoning +
content*, *total = prefill + generation* over the full request span.

#### Reasoning regimes and null conditions

The endpoint's reasoning behaviour determines which client-side metrics are
trustworthy. The regime is always detectable and recorded as
`reasoning_status`:

| `reasoning_status` | Meaning | Detection |
|---|---|---|
| `streamed` | reasoning tokens delivered as stream chunks | `reasoning_chunks > 0` |
| `hidden` | reasoning counted by the server, not streamed | `reasoning_tokens > 0`, no reasoning chunks |
| `none` | no reasoning (off, or non-reasoning model) | `reasoning_tokens == 0` reported |
| `null` | unknown — endpoint reports neither | no signal at all |

Client-side metrics by regime (`✓` = reported, `null` = suppressed):

| Metric | streamed | hidden | none | unknown |
|---|---|---|---|---|
| `timing.ttfc_seconds` | ✓ (first chunk ≈ first generated token) | **null** (absorbs invisible reasoning) | ✓ (authoritative) | **null** |
| `timing.ttfcc_seconds` | ✓ (exact content onset) | ✓ (exact — first chunk *is* content) | ✓ (= ttfc) | **null** |
| `throughput.prefill_cps` | ✓ | **null** | ✓ | **null** |
| `throughput.generation_cps` | ✓ (exact) | **null** (window excludes invisible reasoning time) | ✓ (exact) | **null** |
| `throughput.content_cps` | ✓ (exact) | ✓ (exact content-phase fallback) | ✓ (= generation_cps) | **null** |
| `throughput.total_cps` | ✓ | ✓ | ✓ | **null** (token accounting uncertifiable) |

Server-reported fields (`timing.server.*`, `tokens.*`) are
**regime-independent**: reported whenever the endpoint provides them,
`null` otherwise.

**Rate formulas** (client clock, all in tokens/second):

- `prefill_cps` = `input_tokens / ttfc`
- `generation_cps` = `output_tokens / (total_seconds − ttfc)`
- `content_cps` = `(output_tokens − reasoning_tokens) / (total_seconds − ttfcc)`
- `total_cps` = `(input_tokens + output_tokens) / total_seconds`

**Guards**: `prefill_cps`, `generation_cps` and `content_cps` are nulled when
delivery is buffered (`chunks.output_chunks ≤ 2` — phase boundaries become
meaningless) or when their window is below 1.0 s (quantisation noise).
`total_cps` is exempt from both: its window (`t0 → stream end`) is real in
every delivery mode.

!!! note "The two 'first chunk' metrics"
    `ttfc_seconds` (first *output* chunk) and `ttfcc_seconds` (first
    *content* chunk) are both real and mean different things. With streamed
    reasoning, ttfc lands on the first reasoning token (≈ model onset) and
    ttfcc on the first visible answer token (user-perceived); their
    difference is the visible reasoning duration. With hidden reasoning,
    ttfc is unreliable (nulled) while ttfcc remains exact. With no
    reasoning they are identical. Note `server.user_visible_ttft_seconds` is
    time to the first SSE event on the wire, **not** comparable to client
    `ttfc_seconds`, which requires an *output* chunk.

!!! note "Retries and failed attempts"
    `total_seconds` and `ttfc_seconds`/`ttfcc_seconds` reflect the successful
    request only — a request that timed out and was retried contributes its
    retry wait to `wall_seconds` but nothing to the timing or throughput
    fields.

#### Run-Level Aggregates (`metrics.operational`)

The run-level `operational` object mirrors the per-task nesting:

- `operational.timing` — `total_seconds` (summed) and `wall_seconds`
  (summed), plus for each of `ttfc_seconds` and `ttfcc_seconds` a
  `_mean` / `_min` / `_max` across the tasks that reported a value
  (`null` when none did).
- `operational.timing.server` — for each server field a `_mean` / `_min` /
  `_max`; keys always exist, values are `null` when the endpoint does not
  provide the checkpoint. When present, the authoritative decode rate from
  the aggregate: `1 / engine_tbt_seconds_mean` ≈ tokens/s.
- `operational.throughput` — for each client-derived rate (`prefill_cps`,
  `generation_cps`, `content_cps`, `total_cps`) a `_mean` / `_min` / `_max`
  across tasks that reported a value. Mean/min/max are over per-task values,
  not recomputed from summed tokens — so they are insensitive to differences
  in task duration.
- `operational.tokens` — summed `input_tokens`, `output_tokens`,
  `total_tokens`.
- `operational.reasoning_status` — the regime observed on the run (first
  non-null per-task status).

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

**Criteria Evaluation**: `metrics.normalized_score`, `metrics.criteria_scores`, `metrics.dimension_scores`.

**Criteria Evaluation (absolute)**: `metrics.normalized_score`, `metrics.earned_points`, `metrics.max_points`, `metrics.dimension_scores`.

**Instruction Following**: `metrics.score`, `metrics.satisfied`, `metrics.total`.

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

### Criteria Evaluation (DeepResearchBench)

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
            "per_dimension_avg": {"content_quality": 2.35, "writing": 1.8},
            "per_criteria_avg": {
                "content_quality": {"instruction_following": 3.2, "comprehensiveness": 1.5},
                "writing": {"clarity": 2.1, "structure": 1.5}
            }
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
            "actual": "Paris",
            "is_correct": true,
            "is_skipped": false,
            "skip_reason": null,
            "reasoning": "The answer matches the reference.",
            "elapsed_time": 2.3
        },
        "task_002": {
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
