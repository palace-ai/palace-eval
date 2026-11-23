# info.json Schema Reference

Complete reference for the `info.json` metadata file in a palace tasklist.

## Common Fields (All Task Types)

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | Yes | string | Display name of the tasklist |
| `task_type` | Yes | string | One of: `"QA"`, `"Classification"`, `"Criteria Evaluation"`, `"Instruction Following"`, `"Agentic"` |
| `category` | No | string | Grouping category (e.g., "Safety", "Reasoning", "Code Generation", "Tool Use", "Deep Research") |
| `subcategory` | No | string | More specific grouping within category |
| `input_modalities` | No | string[] | Input types: `["text"]`, `["text", "image"]`, etc. |
| `output_modalities` | No | string[] | Output types: `["text"]` (most common) |

## HuggingFace Metadata Fields

Include these when the tasklist was downloaded from HuggingFace:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | HuggingFace dataset ID (e.g., `"cais/mmlu"`, `"jrc-ai/GuardBench-EN"`) |
| `original` | boolean | `true` if you created this dataset, `false` if sourced from HuggingFace |
| `version` | string | Semantic version (e.g., `"1.0.0"`) — use for original datasets |
| `config` | string | HuggingFace dataset config/subset name (e.g., `"all"`, `"default"`) |
| `split` | string | HuggingFace split name (e.g., `"test"`, `"train"`, `"validation"`) |

## task_type_fields (Per Task Type)

### QA

QA tasklists typically have NO `task_type_fields` — verification uses the LLM judge directly comparing model answer against `expected`.

Optional:
```json
{
  "task_type_fields": {
    "correctness_criterion": "Custom instruction for the judge about what constitutes a correct answer",
    "references": "Additional context the judge should consider"
  }
}
```

### Classification

```json
{
  "task_type_fields": {
    "labels": [
      {
        "name": "LabelName",
        "description": "What this label measures",
        "classes": [
          {"name": "ClassName1", "condition": "when to assign this class"},
          {"name": "ClassName2", "condition": "when to assign this class"}
        ]
      }
    ]
  }
}
```

**Multiple labels** (multi-label classification): Add multiple objects to the `labels` array.

**Dynamic classes from data** (e.g., multiple-choice with varying options per task):
```json
{
  "task_type_fields": {
    "labels": [
      {
        "name": "Answer",
        "description": "The correct answer to the multiple-choice question."
      }
    ]
  }
}
```
When no `classes` array is provided at tasklist level, each task provides its own via per-task `task_type_fields` override.

### Criteria Evaluation

```json
{
  "task_type_fields": {
    "dimensions": [
      {
        "name": "dimension_name",
        "weight": 0.5,
        "criteria": [
          {
            "name": "criterion_name",
            "description": "What this criterion evaluates",
            "weight": 0.3
          }
        ]
      }
    ]
  }
}
```

- Dimension weights should sum to 1.0
- Criterion weights within a dimension should sum to 1.0
- The LLM judge scores each criterion on a 1-5 scale

### Instruction Following

```json
{
  "task_type_fields": {
    "constraints_from_columns": {
      "types_column": "instruction_id_list",
      "params_column": "kwargs"
    }
  }
}
```

This is used for HuggingFace-sourced datasets (e.g., IFEval) where constraints come from dataset columns. For manually-created tasklists, put constraints directly in each task's `task_type_fields`.

### Agentic

Agentic tasklists have NO `task_type_fields` in info.json. Runtime configuration
lives in `environment/spec.json` instead; info.json carries evaluation metadata only.

## Environment Configuration (Agentic Only)

Environments are declared with `spec.json` files, discovered by palace the same
way vivarium parses them:

- `environment/spec.json` — single environment (most common)
- `environment/<name>/spec.json` — one environment per directory; tasks select
  one via the `"env": "<name>"` field in tasks.json

### Single Environment (most common)

`environment/spec.json`:

```json
{
  "machines": {
    "agent": {
      "image": "python:3.11-slim",
      "networks": ["external"],
      "resources": {"memory": "4g", "cpus": 2}
    }
  },
  "networks": {
    "external": {"internet": true}
  },
  "tools": ["bash", "read", "write", "edit", "grep", "glob", "ls"],
  "custom_tools": ["tools/my_tool.py"],
  "agent_instructions": "System prompt for the agent (optional)"
}
```

### Multiple Environments (e.g., per-task Docker images)

```
environment/
├── env-python-repo/
│   └── spec.json
└── env-js-repo/
    └── spec.json
```

`environment/env-python-repo/spec.json`:

```json
{
  "machines": {
    "agent": {
      "image": "registry/image:python-tag",
      "networks": ["external"],
      "resources": {"memory": "8g", "cpus": 2}
    }
  },
  "networks": {
    "external": {"internet": true}
  }
}
```

When multiple environments exist, each task MUST have `"env": "env-name"` pointing to its environment directory.

### spec.json Keys

| Key | Required | Type | Description |
|-----|----------|------|-------------|
| `machines` | No (by default) | object | Maps machine names to their configuration. Omitted → single default `agent` machine on vivarium's `vivarium-env` image. |
| `networks` | No | object | Network definitions. Default: single `internal` network without internet. |
| `tools` | No | string[] | Built-in vivarium tools to enable. Default set: `bash`, `read`, `write`, `edit`, `grep`, `glob`, `ls`, `web_search`, `web_fetch`, `notify`, `delegate` |
| `custom_tools` | No | string[] | Paths to custom tool files relative to `environment/` |
| `agent_instructions` | No | string | System prompt prepended to agent's context |
| `agent_machine` | No | string | Machine the agent runs on (defaults to the first machine) |
| `vscode` | No | object | VS Code server configuration |

### Machine-Level Keys

| Key | Type | Description |
|-----|------|-------------|
| `image` | string | Docker image name or `./Dockerfile` to build from the environment directory |
| `networks` | string[] | Networks the machine attaches to |
| `resources` | object | Resource limits: `memory` (e.g., `"4g"`), `cpus` (e.g., `2`), `pids` |
| `security` | object | Security options |
| `gpu` | object | GPU configuration |

!!! note
    A per-machine `idle` key is accepted but ignored — machine lifecycle is role-based.

## Complete Examples

### Minimal QA
```json
{
  "name": "MyQA",
  "task_type": "QA",
  "category": "General Knowledge",
  "input_modalities": ["text"],
  "output_modalities": ["text"]
}
```

### Classification with Binary Labels
```json
{
  "name": "SafetyBench",
  "id": "org/SafetyBench",
  "version": "1.0.0",
  "original": true,
  "category": "Safety",
  "task_type": "Classification",
  "task_type_fields": {
    "labels": [
      {
        "name": "Unsafe",
        "description": "Whether the content is unsafe or harmful.",
        "classes": [
          {"name": "Yes", "condition": "if the content is unsafe"},
          {"name": "No", "condition": "if the content is safe"}
        ]
      }
    ]
  }
}
```

### Agentic Tasklist

info.json (evaluation metadata only):
```json
{
  "name": "My-Agent-Bench",
  "task_type": "Agentic",
  "category": "Tool Use"
}
```

environment/spec.json (runtime configuration):
```json
{
  "machines": {
    "agent": {
      "image": "python:3.11-slim",
      "networks": ["external"],
      "resources": {"memory": "4g", "cpus": 2}
    }
  },
  "networks": {
    "external": {"internet": true}
  },
  "tools": ["bash", "read", "write", "edit"],
  "custom_tools": ["tools/query_db.py", "tools/send_email.py"]
}
```

Note: Runtime configuration is in `environment/spec.json`, not in `info.json`.
