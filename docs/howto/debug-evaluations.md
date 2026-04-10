# How to Debug Evaluations

This guide helps you troubleshoot common issues when running PALACE evaluations.

## Common Issues

### Task Failures

When tasks fail unexpectedly, check the reasoning field in results:

```bash
# Find failed tasks in detailed_report
cat results.jsonl | jq '.detailed_report | to_entries[] | select(.value.is_correct == false)'
```

Each task in `detailed_report` includes:

```json
{
    "objective": "What is the capital of Italy?",
    "expected": "Rome",
    "actual": "Milan is the largest city in Italy.",
    "is_correct": false,
    "reasoning": "The answer mentions Milan, which is not the capital...",
    "elapsed_time": 1.2
}
```

The `reasoning` field explains why the judge marked it incorrect.

### QA Judge Issues

**Problem**: Judge marks correct answers as incorrect.

**Diagnosis**:
1. Check the criterion description—is it specific enough?
2. Review the reference answer—does it clearly represent correctness?
3. Examine the reasoning—what did the judge misunderstand?

**Solutions**:

- Make the criterion description more specific:
  ```json
  // Before
  {"description": "The answer is correct."}
  
  // After
  {"description": "The answer contains the same key factual information as the reference, even if phrased differently."}
  ```

- Add incorrect references to help the judge understand boundaries:
  ```json
  {"references": {"correct": ["expected"], "incorrect": ["common_mistake"]}}
  ```

### Classification Parsing Issues

**Problem**: Classification tasks fail even when the model seems correct.

**Diagnosis**: Check if the model output matches the expected XML format exactly.

```json
{
    "actual": "<Unsafe>\n yes \n</Unsafe>",
    "is_correct": false
}
```

**Common causes**:

1. **Case mismatch**: "yes" vs "Yes" — comparison is case-sensitive
2. **Missing tags**: Model didn't use XML format
3. **Wrong tag name**: `<unsafe>` vs `<Unsafe>`

**Solutions**:

- Ensure class names in your config match exactly what you expect
- Check that label names are consistent between info.json and tasks.json
- Review the generated prompt to see what format the model was asked for

### Report Generation Scoring

**Problem**: Reports score unexpectedly low or high.

**Diagnosis**: Check per-criterion scores in the metrics:

```json
{
    "metrics": {
        "criteria_scores": {
            "accuracy": -3,
            "completeness": 2,
            "clarity": 1
        }
    }
}
```

Negative scores mean the reference was better for that criterion. For hierarchical tasklists, criteria are nested by dimension (e.g., `"content_quality": {"accuracy": -3, "completeness": 2}`).

**Solutions**:

- Review criterion descriptions—are they clear and specific?
- Check if weights match your priorities
- Examine the reference report—is it actually high quality?

## Verbose Logging

PALACE outputs evaluation progress to the console using rich formatting. To see detailed per-task output including prompts, model responses, and judge verdicts, reduce the task limit and observe the console output:

```bash
palace-run -u https://api.example.com/v1 -m gpt-4o -t MyBenchmark -l 3
```

Or in Python:

```python
from palace import evaluate

evaluate(
    run_name="debug",
    output_folder="./debug-results",
    url="https://api.example.com/v1",
    name="gpt-4o",
    tasklist="MyBenchmark",
    limit=3,
)
```

This shows:

- Prompts sent to the model
- Raw model responses
- Judge inputs and outputs
- Parsing steps

## Inspecting Prompts

### QA Prompts

The model receives:

```
Provide the direct answer, without any additional text:

{objective}
```

### Classification Prompts

View the generated prompt by checking verbose output or:

```python
from palace.task_types.classification import ClassificationTask
from palace.task_types.base import Task

task = Task.from_dict({"id": "test", "objective": "Test content", "task_type": "Classification", ...})
print(task.adapt_prompt())
```

### Judge Prompts

For QA tasks, the judge sees a prompt constructed from your criterion and references. Run with `-l 1` to see the full evaluation output including judge inputs.

## Testing Individual Tasks

Test a single task to isolate issues:

```bash
palace-run -u https://api.example.com/v1 -m gpt-4o -t MyBenchmark -l 1
```

Or create a minimal test tasklist:

```json
// test-tasks.json
[
    {
        "id": "debug_001",
        "objective": "Your test question",
        "expected": "Expected answer"
    }
]
```

## Validating JSON

Ensure your JSON files are valid:

```bash
python -c "import json; json.load(open('info.json')); json.load(open('tasks.json')); print('Valid!')"
```

Common JSON issues:

- Trailing commas (not allowed in JSON)
- Unescaped quotes in strings
- Missing commas between array elements

## API Issues

### Connection Errors

```bash
# Test API connectivity
curl -H "Authorization: Bearer $OPENAI_LIKE_API_KEY" \
     "$OPENAI_LIKE_API_BASE_URL/models"
```

### Rate Limiting

If you see 429 errors:

- PALACE retries automatically with exponential backoff
- Use `-l` to run fewer tasks per session
- Check your API tier limits

### Timeout Errors

For long-running tasks (especially Report Generation):

- Check if the model is responding slowly
- Consider using a faster model for testing
- Verify network stability

## Comparing Results

### Across Runs

```python
import json

def load_results(path):
    with open(path) as f:
        results = [json.loads(l) for l in f]
    # Flatten detailed_report from all runs
    all_tasks = {}
    for run in results:
        all_tasks.update(run.get("detailed_report", {}))
    return all_tasks

run1 = load_results("results_run1.jsonl")
run2 = load_results("results_run2.jsonl")

# Find tasks with different outcomes
for task_id in run1:
    if task_id in run2 and run1[task_id]["is_correct"] != run2[task_id]["is_correct"]:
        print(f"Changed: {task_id}")
        print(f"  Run 1: {run1[task_id]['is_correct']}")
        print(f"  Run 2: {run2[task_id]['is_correct']}")
```

### Across Models

```python
import json

# Compare accuracy across models
models = ["gpt-4o", "claude-3", "llama-3"]
for model in models:
    with open(f"results_{model}.jsonl") as f:
        results = [json.loads(l) for l in f]
    for run in results:
        report = run.get("detailed_report", {})
        correct = sum(1 for r in report.values() if r["is_correct"])
        print(f"{model}: {correct}/{len(report)}")
```

## Getting Help

If you're stuck:

1. Check the [task type documentation](../task-types/index.md) for your task type
2. Review the [examples](../examples/index.md) for similar benchmarks
3. Run with `-l 1` and examine the full console output
4. Create a minimal reproduction case

---

## Related Pages

- [Run Evaluations](run-evaluations.md) — Running evaluations
- [Custom Criteria](custom-criteria.md) — Configuring evaluation criteria
- [Task Types](../task-types/index.md) — Understanding task types
