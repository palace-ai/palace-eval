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

The adapted prompt is sent to the model via the configured API.

**Text-only tasks:**
```
Request:
  POST {url}/chat/completions
  Authorization: Bearer {token}
  Body: {"messages": [{"role": "user", "content": "{prompt}"}]}
```

**Multimodal tasks (with image attachment):**
```
Request:
  POST {url}/chat/completions
  Body: {
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "{prompt}"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
      ]
    }]
  }
```

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

**Report Generation**: LLM pairwise comparison
```
1. Compare generated report vs reference
2. For each criterion, judge which is better
3. Run comparison twice (swap positions)
4. Aggregate weighted scores
5. Task passes if generated scores higher
```

### 6. Results

Results are saved as JSONL. Each line is a complete evaluation run:

```json
{
    "agent": "gpt-4o",
    "tasklist": "GuardBench-EN",
    "accuracy": 0.85,
    "metrics": {"task_count": 20, "correct_count": 17, "total_time": 120.5},
    "detailed_report": {
        "task_001": {
            "actual": "...",
            "is_correct": true,
            "reasoning": "...",
            "elapsed_time": 1.2
        }
    }
}
```

## Multimodal Support

PALACE supports evaluating vision-language models on tasks with image attachments.

### Supported Formats

| Type | Extensions | Handling |
|------|------------|----------|
| Text | `.txt`, `.md`, `.json`, etc. | Prepended to prompt |
| Image | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` | Sent via Vision API |
| Other | `.mp4`, `.pdf`, etc. | Skipped with warning |

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

- **QA**: Fixed format ("Provide the direct answer..."). Can be overridden via [I/O adapters](../howto/model-adapters.md).
- **Classification**: Controlled by `labels` configuration
- **Report Generation**: Fixed format ("Generate a detailed report..."). Can be overridden via [I/O adapters](../howto/model-adapters.md).

### Verification

- **QA**: Customize via `correctness_criterion` and `references`
- **Classification**: Customize via `labels` and `classes`
- **Report Generation**: Customize via `criteria` or `dimensions`

### Model Configuration

- API endpoint: `-u` / `--url` argument (required for `palace-run`)
- Authentication: `-k` / `--token` argument
- Model selection: `-m` / `--name` argument (required for `palace-run`)

### Judge Configuration (QA, Report Generation)

The judge uses the same API endpoint configured via environment variables:

- API endpoint: `OPENAI_LIKE_API_BASE_URL`
- Authentication: `OPENAI_LIKE_API_KEY`
- Model: `JUDGE_MODEL` (default: minimax-m2)

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
