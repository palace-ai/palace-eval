# info.json Reference

Complete specification for the `info.json` tasklist metadata file.

## Overview

Every PALACE tasklist requires an `info.json` file that defines metadata and evaluation configuration. This file tells PALACE how to interpret and evaluate the tasks.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name for the tasklist |
| `id` | string | Unique identifier (typically `org/name` format) |
| `task_type` | string | One of: `"QA"`, `"Classification"`, `"Report Generation"` |

## Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `version` | string | `"1.0.0"` | Semantic version |
| `category` | string | `""` | Grouping category |
| `original` | boolean | `false` | Whether this is an original PALACE benchmark |
| `task_type_fields` | object | `{}` | Task-type-specific configuration |

## Minimal Example

```json
{
    "name": "MyBenchmark",
    "id": "my-org/MyBenchmark",
    "task_type": "QA"
}
```

## Complete Example

```json
{
    "name": "GuardBench-EN",
    "id": "jrc-ai/GuardBench-EN",
    "version": "1.0.0",
    "original": true,
    "category": "Safety",
    "task_type": "Classification",
    "task_type_fields": {
        "labels": [
            {
                "name": "Unsafe",
                "description": "Content that is unsafe or potentially harmful.",
                "classes": [
                    {"name": "Yes", "condition": "if the prompt contains unsafe content"},
                    {"name": "No", "condition": "if the prompt does not contain unsafe content"}
                ]
            }
        ]
    }
}
```

## Field Details

### name

Display name shown in the CLI and results.

```json
{"name": "My Benchmark Name"}
```

### id

Unique identifier, typically in `organization/name` format for HuggingFace compatibility.

```json
{"id": "jrc-ai/GuardBench-EN"}
```

### version

Semantic version string (major.minor.patch).

```json
{"version": "1.0.0"}
```

### category

Grouping category for organization.

```json
{"category": "Safety"}
```

Common categories: Safety, Knowledge, Reliability, Agentic, Deep Research

### task_type

Determines how tasks are evaluated. Must be one of:

| Value | Description |
|-------|-------------|
| `"QA"` | Semantic verification with LLM judge |
| `"Classification"` | Exact-match categorical outputs |
| `"Report Generation"` | Pairwise comparison with weighted criteria |

### task_type_fields

Configuration specific to the task type. See [Task Type Fields Reference](task-type-fields.md) for complete documentation.

## Task Type Defaults

### QA (no task_type_fields)

```json
{
    "task_type": "QA"
}
```

Defaults to:
- Criterion: "semantic equivalence"
- References: `{"correct": ["expected"], "incorrect": []}`

### Classification (task_type_fields required)

```json
{
    "task_type": "Classification",
    "task_type_fields": {
        "labels": [...]  // Required
    }
}
```

### Report Generation (no task_type_fields)

```json
{
    "task_type": "Report Generation"
}
```

Defaults to standard criteria: instruction_following, comprehensiveness, completeness, writing_quality.

---

## Related Pages

- [tasks.json Reference](tasks-json.md) — Task file specification
- [Task Type Fields Reference](task-type-fields.md) — Configuration options by task type
- [Your First Benchmark](../getting-started/first-benchmark.md) — Creating a tasklist
