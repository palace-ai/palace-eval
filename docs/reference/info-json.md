# info.json Reference

Complete specification for the `info.json` tasklist metadata file.

## Overview

Every PALACE tasklist requires an `info.json` file that defines metadata and evaluation configuration. This file tells PALACE how to interpret and evaluate the tasks.

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name for the tasklist |
| `id` | string | Unique identifier (typically `org/name` format) |
| `task_type` | string | One of: `"QA"`, `"Classification"`, `"Criteria Evaluation"`, `"Instruction Following"`, `"Agentic"` |

## Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format_version` | string | `"1.0"` | PALACE format version (for forward compatibility) |
| `version` | string | `"1.0.0"` | Benchmark/tasklist version (semantic versioning) |
| `category` | string | `""` | Grouping category |
| `original` | boolean | `false` | `true` for custom-built PALACE tasklists, `false` for auto-converted public benchmarks |
| `task_type_fields` | object | `{}` | Task-type-specific configuration |
| `input_modalities` | array | `["text"]` | Input data types in tasks: `"text"`, `"image"`, `"video"`, `"audio"`. Auto-detected by `palace download` from task attachments. |
| `output_modalities` | array | `["text"]` | Expected output data types: `"text"`, `"image"`, `"video"`, `"audio"`. Defaults to `["text"]`. |

## Minimal Example

```json
{
    "name": "MyBenchmark",
    "id": "my-org/MyBenchmark",
    "task_type": "QA",
    "original": true
}
```

## Complete Example

```json
{
    "name": "GuardBench-EN",
    "id": "jrc-ai/GuardBench-EN",
    "format_version": "1.0",
    "version": "1.0.0",
    "original": true,
    "category": "Safety",
    "input_modalities": ["text"],
    "output_modalities": ["text"],
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

### format_version

The PALACE format version this tasklist uses. Allows future format changes while maintaining backward compatibility.

```json
{"format_version": "1.0"}
```

Current version is `"1.0"`. PALACE will read tasklists without this field as format version 1.0.

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

### input_modalities

List of input data types present in the tasklist's tasks. Auto-detected by `palace download` from task attachment file extensions. Always includes `"text"`.

```json
{"input_modalities": ["text", "image"]}
```

Supported values: `"text"`, `"image"`, `"video"`, `"audio"`. PDF attachments count as `"text"` (auto-extracted by PALACE). If `input_modalities` already exists in `info.json` (e.g., custom tasklists), `palace download` preserves the existing value.

!!! note "Backward compatibility"
    The legacy `modalities` key is still read as `input_modalities` if the new key is absent.

### output_modalities

List of output data types the tasklist expects from the model. Defaults to `["text"]`.

```json
{"output_modalities": ["text"]}
```

Supported values: `"text"`, `"image"`, `"video"`, `"audio"`. Unlike input modalities, output modalities are not auto-detected and must be declared manually for non-text output.

Used by palace-gradin for compatibility matching: a model is compatible with a tasklist when `tasklist.input_modalities ⊆ model.input_modalities` AND `tasklist.output_modalities ⊆ model.output_modalities`.

### task_type

Determines how tasks are evaluated. Must be one of:

| Value | Description |
|-------|-------------|
| `"QA"` | Semantic verification with LLM judge |
| `"Classification"` | Exact-match categorical outputs |
| `"Criteria Evaluation"` | Pairwise comparison or absolute rubric scoring |
| `"Instruction Following"` | Deterministic constraint verification |
| `"Agentic"` | Agentic tasks evaluated via Vivarium sandbox |

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

### Criteria Evaluation — Pairwise (no task_type_fields)

```json
{
    "task_type": "Criteria Evaluation"
}
```

Defaults to pairwise mode with standard criteria: instruction_following, comprehensiveness, completeness, writing_quality.

### Criteria Evaluation — Absolute (task_type_fields required)

```json
{
    "task_type": "Criteria Evaluation",
    "task_type_fields": {
        "mode": "absolute"
    }
}
```

Criteria are defined per-task in `tasks.json`. See [Task Type Fields Reference](task-type-fields.md#criteria-evaluation).

### Instruction Following (no task_type_fields)

```json
{
    "task_type": "Instruction Following"
}
```

Constraints are defined per-task in `tasks.json`. No info-level configuration needed.

## Multimodal Example

A tasklist with image attachments (auto-detected by `palace download`):

```json
{
    "name": "VLSBench",
    "id": "Foreshhh/vlsbench",
    "task_type": "Classification",
    "input_modalities": ["text", "image"],
    "output_modalities": ["text"],
    "task_type_fields": {
        "labels": [...]
    }
}
```

A tasklist with multiple images per task:

```json
{
    "name": "MMMU",
    "id": "MMMU/MMMU",
    "task_type": "Classification",
    "input_modalities": ["text", "image"],
    "output_modalities": ["text"],
    "task_type_fields": {
        "labels": [...]
    }
}
```

Tasks with multiple images use the `attachments` field (list) in `tasks.json`. See [tasks.json Reference](tasks-json.md).

---

## Related Pages

- [tasks.json Reference](tasks-json.md) — Task file specification
- [Task Type Fields Reference](task-type-fields.md) — Configuration options by task type
- [Your First Benchmark](../getting-started/first-benchmark.md) — Creating a tasklist
