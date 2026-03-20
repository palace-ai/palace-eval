# Glossary

Key terms used throughout the PALACE documentation.

## A

### Attachment
A file (image, PDF, etc.) associated with a task, stored in the `task_files/` directory and referenced by filename in the task's `attachment` field.

## C

### Classification
A [task type](task-types/classification.md) for categorical outputs where the model must produce specific labels that are verified by exact match.

### Correctness Criterion
In [QA tasks](task-types/qa.md), the criterion used by the LLM judge to determine if an answer is correct. Configurable via `task_type_fields.correctness_criterion`.

### Criteria
In [Report Generation](task-types/report-generation.md), the dimensions used to evaluate and compare reports (e.g., accuracy, completeness, writing quality).

## D

### Dimension
In Report Generation, a grouping of related criteria with its own weight. Used for hierarchical evaluation structures.

## E

### Expected
The reference answer or output for a task. Used differently by each task type:
- **QA**: Reference answer for semantic comparison
- **Classification**: Not used (labels are in `labels` field)
- **Report Generation**: Reference report for pairwise comparison

### Evaluation
The process of running a model against a tasklist and measuring performance.

## I

### info.json
The metadata file for a tasklist, containing name, task type, and configuration. See [info.json Reference](reference/info-json.md).

## J

### Judge
An LLM used to evaluate model outputs. Used by QA (semantic correctness) and Report Generation (pairwise comparison) task types.

## L

### Labels
In [Classification tasks](task-types/classification.md), the expected categorical outputs defined in `task_type_fields.labels` (schema) and `task.labels` (expected values).

## O

### Objective
The prompt or question given to the model for a task. This is the input the model must respond to.

## Q

### QA
A [task type](task-types/qa.md) for question-answering tasks where an LLM judge verifies semantic correctness against reference answers.

## R

### References
In QA tasks, the fields containing correct and optionally incorrect example answers. Configurable via `task_type_fields.references`.

### Report Generation
A [task type](task-types/report-generation.md) for evaluating long-form content through pairwise comparison with weighted criteria.

## T

### Task
A single evaluation item consisting of an objective (input) and expected output, plus optional metadata.

### Tasklist
A collection of tasks with shared configuration, stored as `info.json` + `tasks.json` in a directory.

### Task Type
The evaluation strategy for a tasklist. One of: `QA`, `Classification`, `Report Generation`. Determines how prompts are adapted and outputs are verified.

### task_type_fields
Configuration specific to a task type, defined in `info.json`. Examples: `labels` for Classification, `criteria` for Report Generation, `correctness_criterion` for QA.

### tasks.json
The file containing the list of tasks for a tasklist. See [tasks.json Reference](reference/tasks-json.md).

## V

### Verification
The process of determining if a model's output is correct. Method depends on task type:
- **QA**: LLM judge semantic comparison
- **Classification**: Exact label match
- **Report Generation**: Pairwise criteria scoring
