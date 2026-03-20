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
- Which task type to use (QA, Classification, Report Generation)
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

**Report Generation:**
```
Generate a detailed report based on the following prompt:

{objective}
```

### 4. Model Call

The adapted prompt is sent to the model via the configured API:

```
Request:
  POST {OPENAI_LIKE_API_BASE_URL}/chat/completions
  Authorization: Bearer {OPENAI_LIKE_API_KEY}
  Body: {"messages": [{"role": "user", "content": "{prompt}"}]}

Response:
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

**Report Generation**: LLM pairwise comparison
```
1. Compare generated report vs reference
2. For each criterion, judge which is better
3. Run comparison twice (swap positions)
4. Aggregate weighted scores
5. Task passes if generated scores higher
```

### 6. Results

Results are saved as JSONL:

```json
{
    "task_id": "task_001",
    "objective": "...",
    "expected": "...",
    "model_output": "...",
    "is_correct": true,
    "reasoning": "...",
    "metrics": {...}
}
```

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
│       │         │  QA:            LLM Judge               │    │
│       │         │  Classification: Exact Match            │    │
│       │         │  Report Gen:    LLM Pairwise            │    │
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

- **QA**: Cannot be customized (fixed format)
- **Classification**: Controlled by `labels` configuration
- **Report Generation**: Cannot be customized (fixed format)

### Verification

- **QA**: Customize via `correctness_criterion` and `references`
- **Classification**: Customize via `labels` and `classes`
- **Report Generation**: Customize via `criteria` or `dimensions`

### Model Configuration

- API endpoint: `OPENAI_LIKE_API_BASE_URL`
- Authentication: `OPENAI_LIKE_API_KEY`
- Model selection: `--model` flag or environment variable

### Judge Configuration (QA, Report Generation)

- Separate endpoint: `JUDGE_API_BASE_URL`
- Separate auth: `JUDGE_API_KEY`
- Model: `JUDGE_MODEL`

## Error Handling

### API Errors

- Connection failures are logged and task is marked as failed
- Rate limiting triggers automatic retry with backoff
- Timeout errors are logged with task context

### Parsing Errors

- **Classification**: If XML tags can't be parsed, task fails
- **QA/Report Gen**: If judge output is malformed, task fails

### Validation Errors

- Invalid JSON in tasklist files causes immediate failure
- Missing required fields are caught at load time

---

## Related Pages

- [Verification Methods](verification.md) — How verification works
- [LLM Judges](llm-judges.md) — How judges evaluate responses
- [Task Types](../task-types/index.md) — Task type details
