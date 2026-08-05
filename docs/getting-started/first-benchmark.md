# Your First Benchmark

This tutorial walks you through creating a complete PALACE benchmark from scratch. You'll build a simple knowledge QA tasklist, run it against a model, and interpret the results.

## What You'll Build

A "European Capitals" benchmark that tests whether a model can correctly answer questions about European capital cities. We'll use the QA task type with semantic equivalence verification.

## Prerequisites

- PALACE installed and configured ([Installation Guide](installation.md))
- A working API endpoint for your model
- Basic familiarity with JSON

## Step 1: Plan Your Benchmark

Before writing any files, think through what you're evaluating:

**What capability are you testing?**
Factual knowledge about European geography.

**What task type fits best?**
QA — because correct answers can be phrased differently ("Paris", "The capital is Paris", "Paris is the capital of France").

**What does success look like?**
The model's answer conveys the same factual information as the reference, regardless of phrasing.

**How many tasks do you need?**
Start small (5-10 tasks) to validate your approach, then expand.

## Step 2: Create the Directory Structure

PALACE tasklists live in your cache directory. Create a folder for your benchmark:

```bash
mkdir -p ~/.cache/palace/tasklists/EuropeanCapitals
cd ~/.cache/palace/tasklists/EuropeanCapitals
```

You'll create two files:
- `info.json` — Benchmark metadata and configuration
- `tasks.json` — The actual evaluation tasks

## Step 3: Write info.json

Create `info.json` with your benchmark's metadata:

```json
{
    "name": "EuropeanCapitals",
    "id": "my-org/EuropeanCapitals",
    "version": "1.0.0",
    "original": true,
    "category": "Knowledge",
    "task_type": "QA"
}
```

Let's break down each field:

| Field | Value | Purpose |
|-------|-------|---------|
| `name` | "EuropeanCapitals" | Display name for the benchmark |
| `id` | "my-org/EuropeanCapitals" | Unique identifier (org/name format) |
| `version` | "1.0.0" | Version tracking for your benchmark |
| `original` | `true` | Set to `true` for custom-built PALACE tasklists (vs. auto-converted public benchmarks) |
| `category` | "Knowledge" | Grouping for organization |
| `task_type` | "QA" | Tells PALACE how to evaluate |

Since we're using QA with default settings, we don't need `task_type_fields`. PALACE will use:
- **Criterion**: "semantic equivalence"
- **Reference**: The `expected` field in each task

## Step 4: Write tasks.json

Create `tasks.json` with your evaluation tasks:

```json
[
    {
        "id": "capitals_001",
        "objective": "What is the capital of France?",
        "expected": "Paris"
    },
    {
        "id": "capitals_002",
        "objective": "What is the capital of Germany?",
        "expected": "Berlin"
    },
    {
        "id": "capitals_003",
        "objective": "What is the capital of Italy?",
        "expected": "Rome"
    },
    {
        "id": "capitals_004",
        "objective": "What is the capital of Spain?",
        "expected": "Madrid"
    },
    {
        "id": "capitals_005",
        "objective": "What is the capital of Poland?",
        "expected": "Warsaw"
    }
]
```

Each task has:

| Field | Purpose |
|-------|---------|
| `id` | Unique identifier for tracking results |
| `objective` | The question sent to the model |
| `expected` | Reference answer for verification |

### Tips for Writing Tasks

- **Use unique IDs**: Include a prefix and number for easy tracking
- **Be clear in objectives**: The model should understand what's being asked
- **Keep references concise**: Include essential information, not exhaustive detail

## Step 5: Validate Your Files

Before running, verify your JSON is valid:

```bash
python -c "import json; json.load(open('info.json')); json.load(open('tasks.json')); print('Valid JSON!')"
```

Check that PALACE recognizes your tasklist:

```bash
palace local
```

You should see "EuropeanCapitals" in the list of local tasklists.

## Step 6: Run the Evaluation

Run your benchmark:

```bash
palace run EuropeanCapitals -m gpt-4o
```

You'll see output like:

```
Running EuropeanCapitals (5 tasks)
[1/5] capitals_001 ✓
[2/5] capitals_002 ✓
[3/5] capitals_003 ✓
[4/5] capitals_004 ✓
[5/5] capitals_005 ✓

Accuracy: 5/5 (100.0%)
Results saved to ~/.cache/palace/results/eval.jsonl
```

## Step 7: Interpret the Results

View the detailed results:

```bash
cat ~/.cache/palace/results/eval.jsonl | python -m json.tool
```

The output contains a `detailed_report` with each task's result (keyed by task ID):

```json
{
    "agent": "gpt-4o",
    "tasklist": "EuropeanCapitals",
    "accuracy": 1.0,
    "metrics": {
        "task_count": 5,
        "evaluated_count": 5,
        "correct_count": 5,
        "skipped_count": 0,
        "total_time": 12.5,
        "task_type": {},
        "agent": {}
    },
    "detailed_report": {
        "capitals_001": {
            "actual": "The capital of France is Paris.",
            "is_correct": true,
            "is_skipped": false,
            "skip_reason": null,
            "reasoning": "The answer correctly identifies Paris as the capital of France..."
        }
    }
}
```

Notice that the model said "The capital of France is Paris" while the reference was just "Paris". The LLM judge correctly determined these are semantically equivalent.

### What If a Task Fails?

If a task is marked incorrect, check the `reasoning` field:

```json
{
    "capitals_003": {
        "actual": "Milan is the largest city in Italy.",
        "is_correct": false,
        "is_skipped": false,
        "skip_reason": null,
        "reasoning": "The answer mentions Milan, which is not the capital of Italy. The reference answer is Rome."
    }
}
```

The reasoning explains why the judge marked it incorrect—helpful for debugging model behavior.

If a task was skipped due to an infrastructure issue (e.g., API timeout), it appears with `is_skipped: true` and a `skip_reason` such as `"agent_error"` or `"no_response"`. Skipped tasks are excluded from the accuracy calculation.

## Step 8: Iterate and Improve

Now that you have a working benchmark, consider improvements:

### Add More Tasks

Expand coverage with more countries:

```json
{
    "id": "capitals_006",
    "objective": "What is the capital of Portugal?",
    "expected": "Lisbon"
}
```

### Add Difficulty Variations

Include less commonly known capitals:

```json
{
    "id": "capitals_010",
    "objective": "What is the capital of Slovenia?",
    "expected": "Ljubljana"
}
```

### Test Edge Cases

Add questions that might trip up models:

```json
{
    "id": "capitals_015",
    "objective": "What is the capital of the Netherlands?",
    "expected": "Amsterdam"
}
```

(Note: The Netherlands' constitutional capital is Amsterdam, though the government sits in The Hague—a potential source of model confusion.)

## Going Further: Custom Criteria

For more nuanced evaluation, you can customize the correctness criterion. For example, if you wanted to require that answers include the country name:

```json
{
    "name": "EuropeanCapitals-Strict",
    "id": "my-org/EuropeanCapitals-Strict",
    "version": "1.0.0",
    "original": true,
    "category": "Knowledge",
    "task_type": "QA",
    "task_type_fields": {
        "correctness_criterion": {
            "name": "complete answer",
            "description": "The answer must correctly identify the capital city AND mention the country name in the response."
        }
    }
}
```

See the [QA Task Type](../task-types/qa.md) guide for more configuration options.

## Summary

You've created a complete PALACE benchmark:

1. **Planned** what capability to test and which task type to use
2. **Created** `info.json` with benchmark metadata (including `original: true`)
3. **Created** `tasks.json` with evaluation tasks
4. **Ran** the evaluation with `palace run`
5. **Interpreted** results including judge reasoning

This same process applies to any benchmark—change the task type and configuration to match your evaluation goals.

---

## Next Steps

- [Task Types](../task-types/index.md) — Learn about QA, Classification, and Criteria Evaluation
- [Custom Criteria](../howto/custom-criteria.md) — Customize how correctness is evaluated
- [Publish to HuggingFace](../howto/publish-huggingface.md) — Share your benchmark with others
