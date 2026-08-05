# Evaluation Pipeline

This page explains how PALACE evaluates models from start to finish.

## Overview

PALACE evaluation follows a consistent pipeline regardless of task type:

```
Tasklist → Task Iteration → Prompt Adaptation → Model Call → Verification → Results
```

Each stage has specific responsibilities and can be customized through configuration.

## Pipeline Stages

### 1. Tasklist Loading

PALACE loads the tasklist from disk:

```
~/.cache/palace/tasklists/{TasklistName}/
├── info.json      # Configuration
└── tasks.json     # Tasks to evaluate
```

The `info.json` determines:
- Which task type to use (QA, Classification, Criteria Evaluation, Instruction Following, Agentic)
- How to configure verification
- Any task-type-specific settings

### 2. Task Iteration

PALACE iterates through each task in `tasks.json`:

```python
for task in tasks:
    result = evaluate_task(task, config)
    results.append(result)
```

Tasks are processed sequentially. The `--limit` option can restrict how many tasks are evaluated.

### 3. Prompt Adaptation

Each task type adapts the prompt differently:

**QA:**
```
Provide the direct answer, without any additional text:

{objective}
```

**Classification:**
```
You have to perform a classification task.
Consider the following text:
-----
{objective}
-----

And consider the following label(s)...
```

**Criteria Evaluation:**
```
Generate a detailed report based on the following prompt:

{objective}
```

**Instruction Following:**
```
{objective}
```

The objective is passed directly — constraints are verified post-hoc, not embedded in the prompt.

### 4. Model Call

The adapted prompt is sent to the model via the configured API.

**Text-only tasks:**
```
Request:
  POST {url}/chat/completions
  Authorization: Bearer {token}
  Body: {"messages": [{"role": "user", "content": "{prompt}"}]}
```

**Multimodal tasks (with image attachments):**
```
Request:
  POST {url}/chat/completions
  Body: {
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "{prompt}"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
      ]
    }]
  }
```

Multiple images are supported (up to 7 per task). Each image attachment is encoded as a separate `image_url` content part.

Images are automatically:
- Resized to max 1024px dimension (to avoid payload limits)
- Converted to JPEG (for oversized images) with 95% quality
- Base64-encoded for the API

**Response:**
```
{"choices": [{"message": {"content": "{model_output}"}}]}
```

### 5. Verification

Verification differs by task type:

**QA**: LLM judge evaluates semantic correctness
```
Judge Input:
  - Question
  - Correct reference(s)
  - Incorrect reference(s) (if any)
  - Model's answer

Judge Output:
  - Reasoning
  - Judgement: Correct or Incorrect
```

**Classification**: Exact string match
```
1. Parse XML tags from model output
2. Extract values for each label
3. Compare exactly against expected labels
4. All labels must match for task to pass
```

**Criteria Evaluation**: LLM pairwise comparison
```
1. Compare generated report vs reference
2. For each criterion, judge which is better
3. Run comparison twice (swap positions)
4. Aggregate weighted scores
5. Task passes if generated scores higher
```

**Criteria Evaluation (absolute)**: LLM per-criterion judgement
```
1. Present objective and response to judge
2. For each criterion, judge answers YES/NO
3. Tally points (positive = reward, negative = penalty)
4. Score = earned / max_positive, clamped [0, 1]
5. Task passes if score ≥ 0.5
```

**Instruction Following**: Deterministic constraint checkers
```
1. For each constraint, run programmatic checker
2. Score = fraction of constraints satisfied
3. Task passes if score ≥ 0.5
```

### 6. Results

Results are saved as JSONL. Each line is a complete evaluation run:

```json
{
    "agent": "gpt-4o",
    "tasklist": "GuardBench-EN",
    "accuracy": 0.85,
    "metrics": {"task_count": 20, "evaluated_count": 20, "correct_count": 17, "skipped_count": 0, "total_time": 120.5, "task_type": {}, "agent": {}},
    "detailed_report": {
        "task_001": {
            "actual": "...",
            "is_correct": true,
            "is_skipped": false,
            "skip_reason": null,
            "reasoning": "...",
            "elapsed_time": 1.2
        }
    }
}
```

## Multimodal Support

PALACE supports evaluating vision-language models on tasks with image attachments, including multiple images per task.

### Supported Formats

| Type | Extensions | Handling |
|------|------------|----------|
| Text | `.txt`, `.md`, `.json`, etc. | Prepended to prompt |
| Image | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` | Sent via Vision API |
| Other | `.mp4`, `.pdf`, etc. | Skipped with warning |

### Multi-Image Tasks

Tasks can have multiple image attachments (up to 7 per task). All images are included in a single API request as separate `image_url` content parts. This is used by benchmarks like MMMU where questions reference multiple figures.

Tasks declare multiple images via the `attachments` field in `tasks.json`:

```json
{"id": "task_001", "objective": "...", "attachments": ["img1.png", "img2.png"]}
```

### Image Processing

Large images are automatically processed before sending:

1. **Resize**: Images larger than 1024px (either dimension) are scaled down
2. **Convert**: Large images converted to JPEG for consistent compression
3. **Encode**: Base64-encoded for the OpenAI Vision API format

This ensures compatibility with API payload limits while preserving image quality.

### Unsupported Attachments

Tasks with unsupported attachment types (video, audio, PDFs, etc.) are automatically skipped with a warning. The evaluation continues with remaining tasks.

### Model Requirements

The target model must support vision inputs. Compatible models include:
- GPT-4o, GPT-4o-mini
- Claude 3+ (Haiku, Sonnet, Opus)
- Gemini Pro Vision
- LLaVA, Qwen-VL (local)

Non-vision models will fail on image tasks.

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     PALACE Evaluation Pipeline                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ Tasklist │───▶│  Prompt  │───▶│  Model   │───▶│  Verify  │  │
│  │  Load    │    │  Adapt   │    │  Call    │    │          │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │                                               │         │
│       │                                               ▼         │
│       │         ┌─────────────────────────────────────────┐    │
│       │         │              Verification               │    │
│       │         ├─────────────────────────────────────────┤    │
│       │         │  QA:              LLM Judge             │    │
│       │         │  Classification:  Exact Match           │    │
│       │         │  Report Gen:      LLM Pairwise          │    │
│       │         │  Criteria Eval:   LLM Absolute Rubric   │    │
│       │         │  Instruction:     Constraint Checkers   │    │
│       │         └─────────────────────────────────────────┘    │
│       │                                               │         │
│       │                                               ▼         │
│       │                                        ┌──────────┐    │
│       └───────────────────────────────────────▶│ Results  │    │
│                    (repeat for each task)      │  JSONL   │    │
│                                                └──────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Customization Points

### Prompt Adaptation

- **QA**: Fixed format ("Provide the direct answer..."). Can be overridden via [I/O adapters](../howto/model-adapters.md).
- **Classification**: Controlled by `labels` configuration
- **Criteria Evaluation**: Fixed format ("Generate a detailed report..."). Can be overridden via [I/O adapters](../howto/model-adapters.md).
- **Instruction Following**: Passes objective directly (no wrapping).

### Verification

- **QA**: Customize via `correctness_criterion` and `references`
- **Classification**: Customize via `labels` and `classes`
- **Criteria Evaluation**: Customize via `criteria` or `dimensions`
- **Criteria Evaluation**: Customize via per-task `criteria` with `points` and `dimension`
- **Instruction Following**: Customize via per-task `constraints` list

### Model Configuration

- API endpoint: `-u` / `--url` argument or `palace config set url`
- Authentication: `-k` / `--token` argument or `palace config set key`
- Model selection: `-m` / `--model` argument

### Judge Configuration (QA, Criteria Evaluation)

The judge model is configured via:

- Config file: `palace config set judge_model gpt-4o`
- Environment variable: `JUDGE_MODEL`

The judge uses the same API endpoint configured for evaluation.

## Error Handling

### Task Failure Handling

When a task fails due to infrastructure issues (API errors, timeouts, empty responses), it is **skipped** rather than marked incorrect. Skipped tasks are excluded from accuracy calculations, ensuring that infrastructure failures don't penalise model scores.

Each skipped task records a machine-readable `skip_reason`:

| Reason | Trigger |
|--------|---------|
| `no_response` | Agent returned empty or whitespace-only response |
| `agent_error` | Agent raised an exception (API error, timeout, etc.) |
| `unsupported_attachment` | Task has an attachment type the model can't process |
| `verification_error` | Judge/verification failed on a valid response |

Skipped tasks appear in the JSONL output with `is_skipped: true` and `is_correct: false`. The run-level metrics report both `evaluated_count` (tasks with real answers) and `skipped_count` separately. Accuracy is computed as `correct_count / evaluated_count`.

### API Errors

- Connection failures trigger retry with exponential backoff
- Rate limiting (429) triggers automatic retry with backoff
- After all retries exhausted, the task is skipped with `agent_error`

### Parsing Errors

- **Classification**: If XML tags can't be parsed, task is marked incorrect (not skipped — the model responded, just badly)
- **QA/Report Gen**: If judge output is malformed, task is skipped with `verification_error`

### Validation Errors

- Invalid JSON in tasklist files causes immediate failure
- Missing required fields are caught at load time

---

## Related Pages

- [Verification Methods](verification.md) — How verification works
- [LLM Judges](llm-judges.md) — How judges evaluate responses
- [Task Types](../task-types/index.md) — Task type details
