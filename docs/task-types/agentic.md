# Agentic

Agentic evaluation is for benchmarks where the model interacts with tools and environments to complete tasks. The agent runs in a sandboxed Docker container with access to tools like bash, file I/O, web search, and more. Verification is performed by an external verifier script that checks the final environment state.

## When to Use Agentic

Choose Agentic when:

- **The model needs to interact with tools** — bash, file system, web search, databases
- **Tasks require multi-step execution** — not just answering a question
- **Correctness depends on environment state** — database entries, file contents, system state
- **You're evaluating coding or computer-use capabilities** — SWE-bench, τ-bench, WebArena

## How It Works

1. **Task loads** — PALACE reads the task from `tasks.json`
2. **Environment seeds** — Vivarium creates a fresh container and runs the seed script to set up initial state
3. **Agent executes** — The model runs in the container, interacting with tools via a ReAct loop
4. **Verification runs** — PALACE calls `verify.py` with the expected outcome and final environment state
5. **Results aggregate** — Accuracy is calculated across all tasks

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Task loads    │────▶│  Environment    │────▶│  Agent runs     │
│   from JSON     │     │  seeds via      │     │  in container   │
│                 │     │  Vivarium       │     │  with tools     │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
┌─────────────────┐     ┌─────────────────┐              │
│   Results       │◀────│   verify.py     │◀─────────────┘
│   aggregate     │     │   checks state  │
└─────────────────┘     └─────────────────┘
```

## Requirements

Agentic evaluation requires additional setup:

- **Docker 24+** — installed and running
- **Vivarium SDK** — `pip install vivarium-ai`

### Start Vivarium

Before running agentic benchmarks:

```bash
vivarium start
vivarium status  # Should show "running"
```

## Tasklist Structure

Agentic tasklists have a special structure:

```
MyAgenticBenchmark/
├── info.json           # task_type: "Agentic"
├── tasks.json          # Tasks with seed_args and expected_outcome
└── environment/
    ├── seed.py         # Sets up initial state for each task
    ├── verify.py       # Verifies correctness after execution
    └── verify_files/   # Optional: tamper-proof files copied at verify time
        └── task_001/
            └── expected.txt
```

### info.json

```json
{
    "name": "MyAgenticBenchmark",
    "id": "my-org/MyAgenticBenchmark",
    "format_version": "1.0",
    "task_type": "Agentic",
    "category": "Agentic",
    "subcategory": "Tool Use"
}
```

### tasks.json

Each task specifies:

- `objective` — What the agent should accomplish
- `seed_args` — Arguments passed to `seed.py` to set up initial state
- `expected_outcome` — Expected final state passed to `verify.py`

```json
[
    {
        "id": "task_001",
        "objective": "Create a file named 'output.txt' containing 'Hello World'",
        "seed_args": {},
        "expected_outcome": {
            "file_path": "/workspace/output.txt",
            "expected_content": "Hello World"
        }
    }
]
```

### seed.py

Sets up the environment before the agent runs:

```python
def seed(container, args: dict) -> None:
    """Seed the environment for a task.
    
    Args:
        container: Vivarium container with exec/read/write methods
        args: The task's seed_args from tasks.json
    """
    # Example: create initial files, populate databases, etc.
    if "initial_file" in args:
        container.write("/workspace/input.txt", args["initial_file"])
```

### verify.py

Checks correctness after the agent finishes:

```python
def verify(expected: dict, answer: str, container) -> bool | dict:
    """Verify the task outcome.
    
    Args:
        expected: The task's expected_outcome from tasks.json
        answer: The agent's final response
        container: Vivarium container to inspect final state
        
    Returns:
        bool: True if correct, False otherwise
        dict: {"is_correct": bool, "reasoning": str, "metrics": dict}
    """
    file_path = expected.get("file_path")
    expected_content = expected.get("expected_content")
    
    try:
        actual = container.read(file_path)
        return actual.strip() == expected_content.strip()
    except Exception as e:
        return {"is_correct": False, "reasoning": f"File not found: {e}"}
```

## Verification Return Values

`verify.py` can return:

| Return Type | Interpretation |
|-------------|----------------|
| `True` / `False` | Simple pass/fail |
| `float` (0.0–1.0) | Partial credit; ≥1.0 is correct |
| `dict` | Full control: `is_correct`, `reasoning`, `metrics` |

### Example: Partial Credit

```python
def verify(expected: dict, answer: str, container) -> dict:
    tests_passed = run_test_suite(container)
    total_tests = expected["total_tests"]
    score = tests_passed / total_tests
    
    return {
        "is_correct": score >= expected.get("pass_threshold", 1.0),
        "reasoning": f"Passed {tests_passed}/{total_tests} tests",
        "metrics": {"tests_passed": tests_passed, "score": score}
    }
```

## Metrics

Agentic evaluation tracks additional metrics:

| Metric | Description |
|--------|-------------|
| `accuracy` | Fraction of tasks passed |
| `avg_steps` | Average ReAct loop iterations |
| `avg_tool_calls` | Average tool invocations per task |
| `avg_duration_seconds` | Average wall-clock time per task |

## Running Agentic Evaluations

```bash
# Start Vivarium first
vivarium start

# Run evaluation
palace run MyAgenticBenchmark -m gpt-4o

# Stop Vivarium when done
vivarium stop
```

## Example Benchmarks

PALACE supports several agentic benchmarks:

| Benchmark | Description |
|-----------|-------------|
| τ-bench (Tau2) | Database operations in simulated retail/airline environments |
| SWE-bench | Real GitHub issue resolution in Python repositories |
| CyBench | Capture-the-flag security challenges |

These require downloading via conversion scripts — see their documentation in `palace-eval/src/palace/data_utils/`.

## Common Patterns

### Database Verification

```python
def verify(expected: dict, answer: str, container) -> dict:
    # Query final database state
    result = container.exec("sqlite3 /data/app.db 'SELECT * FROM orders'")
    
    # Parse and compare
    rows = parse_sqlite_output(result.stdout)
    expected_rows = expected["expected_orders"]
    
    return {
        "is_correct": rows == expected_rows,
        "reasoning": f"Found {len(rows)} orders, expected {len(expected_rows)}"
    }
```

### File Diff Verification

```python
def verify(expected: dict, answer: str, container) -> dict:
    # Read generated file
    actual = container.read(expected["output_file"])
    
    # Compare against reference (from verify_files/)
    reference = container.read(f"/verify_files/{expected['reference_file']}")
    
    # Use diff for comparison
    import difflib
    diff = list(difflib.unified_diff(reference.splitlines(), actual.splitlines()))
    
    return {
        "is_correct": len(diff) == 0,
        "reasoning": "\n".join(diff) if diff else "Files match"
    }
```

### Test Suite Verification

```python
def verify(expected: dict, answer: str, container) -> dict:
    # Run pytest in container
    result = container.exec("cd /workspace && pytest --tb=short")
    
    # Parse test results
    passed = "passed" in result.stdout and "failed" not in result.stdout
    
    return {
        "is_correct": passed,
        "reasoning": result.stdout[-500:],  # Last 500 chars of output
        "metrics": {"exit_code": result.returncode}
    }
```

## Troubleshooting

### "No execution environment"

Vivarium isn't running or isn't accessible:

```bash
vivarium status  # Check status
vivarium start   # Start if not running
```

### "No verify function"

The tasklist is missing `environment/verify.py`:

```bash
ls MyAgenticBenchmark/environment/
# Should show: seed.py verify.py
```

### Container Errors

Check Vivarium logs:

```bash
docker logs vivarium-server
```

---

## Related Pages

- [Installation](../getting-started/installation.md#agentic-evaluation-optional) — Setting up Vivarium
- [Run Evaluations](../howto/run-evaluations.md) — Running benchmarks
- [VivariumAgent API](../reference/api/agents.md) — Programmatic agent control
