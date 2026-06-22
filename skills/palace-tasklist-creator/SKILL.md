---
name: palace-tasklist-creator
description: >
  Create palace-lib evaluation tasklists (benchmarks) from scratch or from HuggingFace datasets.
  Covers all 5 task types: QA, Classification, Criteria Evaluation, Instruction Following, and Agentic (with vivarium sandboxed containers, custom tools, seed/verify scripts). Use when the user wants to create a new benchmark, build a tasklist, implement an evaluation dataset, or adapt an existing dataset for palace evaluation — even if they don't say "palace" explicitly.
compatibility: Requires Python 3.11+ and access to ~/.cache/palace/tasklists/ directory.
metadata:
  author: palace-team
  version: "1.0"
---

# Palace Tasklist Creator

Create evaluation tasklists that palace-lib can run against LLM models/agents.

## What is a Tasklist?

A directory in `~/.cache/palace/tasklists/{Name}/` containing:

```
{Name}/
├── info.json          # Required: metadata + task type config
├── tasks.json         # Required: array of task objects
├── environment/       # Agentic only: seed.py, verify.py, tools/, Dockerfile
└── task_files/        # Optional: attachments (text, images, per-task bundles)
```

## Step 1: Choose Your Path

**Is the benchmark a simple tabular dataset on HuggingFace (columns map directly to palace fields)?**
- YES → Use `palace-download` with column mapping. See [dataset-generation.md](references/dataset-generation.md).
- NO (complex processing needed, agentic setup, or not on HF) → Write a `create_dataset.py` script or craft `info.json` + `tasks.json` directly. See [dataset-generation.md](references/dataset-generation.md).

## Step 2: Decide the Task Type

| Task Type | Use When | Verification Method |
|-----------|----------|-------------------|
| **QA** | Model answers a question, judged against expected answer | LLM judge compares answer to `expected` |
| **Classification** | Model assigns labels from predefined classes | Exact match against ground-truth `labels` |
| **Criteria Evaluation** | Model generates a report/essay, graded on criteria | LLM judge scores on weighted dimensions |
| **Instruction Following** | Model must follow format constraints | Programmatic constraint checkers |
| **Agentic** | Agent acts in sandboxed environment, outcome verified | Custom `verify.py` checks final state |

## Step 3: Write info.json

Every info.json has these common fields:

```json
{
  "name": "My-Benchmark",
  "task_type": "QA | Classification | Criteria Evaluation | Instruction Following | Agentic",
  "category": "Safety | Reasoning | Code Generation | ...",
  "input_modalities": ["text"],
  "output_modalities": ["text"]
}
```

For full schema including per-type `task_type_fields` and `env` config, read [info-json-schema.md](references/info-json-schema.md).

## Step 4: Write tasks.json

An array of task objects. Every task has:

```json
{
  "id": "unique_task_id",
  "objective": "The prompt or question shown to the model"
}
```

Additional fields depend on task type. For complete per-type schemas and examples, read [tasks-json-schema.md](references/tasks-json-schema.md).

## Step 5: Add Type-Specific Components

- **QA**: Add `expected` field to each task (the correct answer string).
- **Classification**: Add `labels` dict to each task + configure `task_type_fields.labels` in info.json.
- **Criteria Evaluation**: Add `expected` (reference report) + configure `task_type_fields.dimensions` in info.json or per-task.
- **Instruction Following**: Add `task_type_fields.constraints` per task.
- **Agentic**: Create `environment/` with `seed.py` + `verify.py`. Read [agentic-tasklists.md](references/agentic-tasklists.md).

For quick examples of each type, read [task-types.md](references/task-types.md).

## Step 6: Handle Attachments (if needed)

If tasks have associated files (documents, images, code):

1. Create `task_files/` directory in the tasklist
2. Place files there (flat or in per-task subdirectories)
3. Reference via `"attachment": "filename.txt"` or `"attachments": ["file1.png", "subdir/file2.py"]`

Text files (`.txt`, `.md`, `.json`, `.py`, etc.) are prepended to the prompt.
Binary files (images) are sent as multimodal attachments.

## Step 7: Validate

Run the structural validation script:

```bash
python .kiro/skills/palace-tasklist-creator/scripts/validate_tasklist.py /path/to/your/tasklist
```

For **Agentic tasklists**, also run the smoke test to verify the infrastructure actually bootstraps (requires Docker + vivarium SDK):

```bash
python .kiro/skills/palace-tasklist-creator/scripts/smoke_test_tasklist.py /path/to/your/tasklist --task-limit 2
```

The smoke test registers specs, builds/pulls images, creates environments, runs seed.py, and attempts verify.py — all without needing an LLM. It catches Dockerfile errors, broken seed scripts, missing files, and unreachable companions.

Fix any reported errors, then your tasklist is ready for evaluation with `palace-run`.

## Gotchas

- **task_type strings are case-sensitive**: Use exactly `"QA"`, `"Classification"`, `"Criteria Evaluation"`, `"Instruction Following"`, `"Agentic"`.
- **id must be unique** across all tasks in the tasklist.
- **Agentic info.json MUST have `"env"` key**: VivariumAgent raises ValueError without it.
- **seed.py and verify.py must be async**: `async def seed(seed_args, container)` — NOT `def seed(...)`.
- **Custom tool execute() must be async**: `async def execute(args, container, context)` — uses `await container.read(...)`, `await container.write(...)`, `await container.exec(...)`.
- **container methods are async**: `await container.read()` returns str, `await container.write()` takes bytes, `await container.exec()` returns `(code, output)`.
- **task_files/ lands at `/task_files/` in the container** for agentic tasks (vivarium adds prefix). Matched by task ID — do NOT add `"attachment"` field for agentic tasks (causes silent skip).
- **Multi-env tasklists**: When info.json has multiple `env` entries, each task MUST have `"env": "name"` field.
- **Labels in tasks.json**: Maps `label_name → class_name` (e.g., `{"Unsafe": "Yes"}`), NOT booleans.
- **task_type_fields merge**: Tasklist-level fields are overridden by task-level fields (task wins).
- **palace-download column_names**: Maps palace field names to HuggingFace column names (e.g., `{"objective": "question", "expected": "answer"}`).
- **Modalities**: Declare `"input_modalities": ["image", "text"]` if tasks have image attachments.
- **Smoke test vs structural validation**: `validate_tasklist.py` is instant (checks format). `smoke_test_tasklist.py` needs Docker (checks that images build, seed runs, verify loads). Run structural first, smoke test when ready to deliver.
- **Custom images must be self-contained**: If info.json references a custom image name, include a `Dockerfile` in `environment/` so vivarium can build it. Otherwise use a public Docker Hub image (e.g., `python:3.11-slim`). A tasklist referencing a non-buildable, non-public image is broken.
- **Image must have all runtime dependencies**: Everything that seed.py, verify.py, custom tools, or the agent needs (compilers, interpreters, libraries, CLI tools) MUST be installed in the Dockerfile or already present in the base image. If seed.py calls `gcc`, the image must have gcc. If agent_instructions promise `gdb` and `objdump`, the image must have them. A bare `ubuntu:22.04` has almost nothing — always install what you need.

## When to Read Reference Files

| Situation | Read |
|-----------|------|
| Writing info.json (any type) | [references/info-json-schema.md](references/info-json-schema.md) |
| Writing tasks.json (any type) | [references/tasks-json-schema.md](references/tasks-json-schema.md) |
| Building an Agentic tasklist | [references/agentic-tasklists.md](references/agentic-tasklists.md) |
| Need a complete example for a specific type | [references/task-types.md](references/task-types.md) |
| Using palace-download or writing create_dataset.py | [references/dataset-generation.md](references/dataset-generation.md) |

## Templates

Starter templates for each task type are in `assets/templates/`. Copy and adapt:

- `qa-info.json` + `qa-tasks.json`
- `classification-info.json` + `classification-tasks.json`
- `criteria-evaluation-info.json` + `criteria-evaluation-tasks.json`
- `agentic-info.json` + `agentic-tasks.json` + `seed.py` + `verify.py` + `tool-template.py`
