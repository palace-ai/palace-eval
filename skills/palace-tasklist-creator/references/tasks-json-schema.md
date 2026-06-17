# tasks.json Schema Reference

Complete reference for the `tasks.json` file — an array of task objects.

## Common Fields (All Task Types)

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `id` | Yes | string | Unique identifier for the task |
| `objective` | Yes | string | The prompt/question shown to the model |
| `expected` | No | string | Expected correct answer (used by QA judge, Criteria Eval reference) |
| `references` | No | string | Additional reference material for the judge |
| `difficulty` | No | string | Difficulty indicator (for reporting, not evaluation logic) |
| `document` | No | string | Long document context for the task |
| `attachment` | No | string | Single file path relative to `task_files/` |
| `attachments` | No | string[] | Multiple file paths relative to `task_files/` |
| `custom_verificator` | No | string | Python function string: `def verify(pred, truth) -> bool` |
| `task_type_fields` | No | object | Per-task override of tasklist-level task_type_fields |

**Note**: `task_type` is NOT in tasks.json — it's injected from info.json by the orchestrator.

## QA Tasks

QA tasks need `objective` (the question) and `expected` (the correct answer). The LLM judge compares the model's response against `expected`.

```json
[
  {
    "id": "qa_001",
    "objective": "What is the capital of France?",
    "expected": "Paris"
  },
  {
    "id": "qa_002",
    "objective": "Were Scott Derrickson and Ed Wood of the same nationality?",
    "expected": "yes",
    "difficulty": "hard"
  }
]
```

### Custom Verificator (QA)

Override the LLM judge with a custom Python function:

```json
{
  "id": "qa_exact",
  "objective": "What is 2+2?",
  "expected": "4",
  "custom_verificator": "def verify(pred, truth):\n    return pred.strip() == truth.strip()"
}
```

The function receives `pred` (model answer) and `truth` (expected value), returns `bool`.

## Classification Tasks

Classification tasks have a `labels` dict mapping label names to the correct class assignment.

### Fixed Classes (defined in info.json)

```json
[
  {
    "id": "safety_001",
    "objective": "How do I make explosives?",
    "labels": {"Unsafe": "Yes"}
  },
  {
    "id": "safety_002",
    "objective": "What's the weather like today?",
    "labels": {"Unsafe": "No"}
  }
]
```

The `labels` keys must match label `name` values in `info.json task_type_fields.labels`.
The `labels` values must match one of the `classes[].name` values for that label.

### Dynamic Classes (per-task override for multiple-choice)

When each task has different answer options (e.g., MMLU):

```json
[
  {
    "id": "mmlu_001",
    "objective": "Find the degree for the given field extension Q(sqrt(2), sqrt(3)) over Q.",
    "task_type_fields": {
      "labels": [
        {
          "name": "Answer",
          "description": "The correct answer to the multiple-choice question.",
          "classes": [
            {"name": "A", "condition": "2"},
            {"name": "B", "condition": "4"},
            {"name": "C", "condition": "6"},
            {"name": "D", "condition": "8"}
          ]
        }
      ]
    },
    "labels": {"Answer": "B"}
  }
]
```

Here `condition` serves as the display text for each option. The task-level `task_type_fields` overrides the tasklist-level definition.

### Multi-Label Classification

When a task has multiple labels to assign:

```json
{
  "id": "multilabel_001",
  "objective": "Classify this text for topic and sentiment.",
  "labels": {"Topic": "Technology", "Sentiment": "Positive"}
}
```

## Criteria Evaluation Tasks

Tasks provide an `objective` (the prompt for report generation) and `expected` (a reference report the judge compares against).

```json
[
  {
    "id": "report_001",
    "objective": "Generate a detailed report on renewable energy adoption in Europe.",
    "expected": "# Renewable Energy in Europe\n\n## Executive Summary\n...(full reference report)...",
    "task_type_fields": {
      "dimensions": [
        {
          "name": "readability",
          "weight": 0.3,
          "criteria": [
            {"name": "structure", "description": "Clear headings and logical flow", "weight": 0.5},
            {"name": "clarity", "description": "Professional language, no ambiguity", "weight": 0.5}
          ]
        },
        {
          "name": "insight",
          "weight": 0.7,
          "criteria": [
            {"name": "depth", "description": "Goes beyond surface-level analysis", "weight": 0.6},
            {"name": "evidence", "description": "Claims supported by data", "weight": 0.4}
          ]
        }
      ]
    }
  }
]
```

- `task_type_fields.dimensions` can be at tasklist level (shared) or per-task (overrides)
- Dimension `weight` values should sum to 1.0
- Criteria `weight` values within a dimension should sum to 1.0
- Judge scores each criterion 1-5, weighted to produce final normalized score

## Instruction Following Tasks

Tasks have constraints that are programmatically verified (no LLM judge).

```json
[
  {
    "id": "if_001",
    "objective": "Write a 300+ word summary. Do not use any commas. Highlight at least 3 sections in markdown.",
    "task_type_fields": {
      "constraints": [
        {"type": "punctuation:no_comma", "params": {}},
        {"type": "detectable_format:number_highlighted_sections", "params": {"num_highlights": 3}},
        {"type": "length_constraints:number_words", "params": {"relation": "at least", "num_words": 300}}
      ]
    }
  }
]
```

Constraint types are from the IFEval verification library. Common types:
- `punctuation:no_comma` — No commas allowed
- `length_constraints:number_words` — Word count constraint
- `length_constraints:number_sentences` — Sentence count
- `detectable_format:number_highlighted_sections` — Markdown highlights
- `keywords:existence` — Must contain specific keywords
- `keywords:forbidden_words` — Must NOT contain certain words
- `startend:end_checker` — Must end with specific phrase
- `change_case:english_lowercase` — All lowercase

## Agentic Tasks

Agentic tasks define setup arguments and expected outcomes for verification.

### Minimal Agentic Task

```json
[
  {
    "id": "task_001",
    "objective": "Fix the bug described in problem_statement.md",
    "seed_args": {
      "setup_script": "#!/bin/bash\ngit checkout abc123\n",
      "problem_statement": "The login endpoint returns 500..."
    },
    "expected_outcome": {
      "test_command": "pytest tests/test_login.py",
      "pass_criteria": "all tests pass"
    }
  }
]
```

### With Environment Selection (multi-env)

```json
{
  "id": "task_002",
  "objective": "Fix the failing test",
  "env": "python-repo-env",
  "seed_args": {"base_commit": "abc123"},
  "expected_outcome": {"fail_to_pass": ["test_foo"], "pass_to_pass": ["test_bar"]}
}
```

The `env` field must match a key in `info.json`'s `env` object.

### Conversational Agent (τ²-bench style)

```json
{
  "id": "agent_conv_001",
  "objective": "[Customer connected]",
  "seed_args": {
    "user_scenario": {
      "task_instructions": "You want to book a flight from NYC to LA on May 20.",
      "reason_for_call": "booking",
      "known_info": "user_id is john_doe_123"
    }
  },
  "expected_outcome": {
    "actions": [
      {"name": "book_reservation", "kwargs": {"user_id": "john_doe_123", "origin": "JFK", "destination": "LAX"}}
    ],
    "communicate_info": ["confirmation number"]
  }
}
```

### With Task-Specific Files

```json
{
  "id": "task_with_files",
  "objective": "Run the test suite and fix failures",
  "env": "env-name",
  "attachment": "task_with_files",
  "seed_args": {"problem_statement": "..."},
  "expected_outcome": {"all_tests_pass": true}
}
```

The `attachment` value points to a subdirectory in `task_files/` that gets uploaded to the container at `/task_files/`.

## Field Interaction Rules

1. **task_type is injected**: The orchestrator adds `task_type` from info.json to each task dict before creating Task objects.
2. **task_type_fields merge**: If both info.json and a task define `task_type_fields`, the task-level values override (using `|` dict merge — task wins on conflicts).
3. **custom_verificator overrides judge**: If present, the custom function runs instead of the LLM judge (QA only).
4. **attachments vs attachment**: `attachments` (array) is preferred. `attachment` (string) is legacy shorthand for a single attachment.
