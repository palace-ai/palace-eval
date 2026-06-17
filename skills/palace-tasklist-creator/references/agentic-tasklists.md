# Agentic Tasklists Deep Dive

Complete guide for creating Agentic tasklists — benchmarks where an LLM agent acts inside a sandboxed container and its work is verified programmatically.

## Directory Structure

```
MyAgenticBench/
├── info.json                  # Must have "env" key
├── tasks.json                 # Tasks with seed_args + expected_outcome
├── environment/               # Required for Agentic type
│   ├── seed.py               # Prepares container state before agent runs
│   ├── verify.py             # Verifies agent's work after it finishes
│   ├── tools/                # Custom tools (one file per tool)
│   │   ├── tool_one.py
│   │   └── tool_two.py
│   ├── data/                 # Static data files (loaded by seed.py)
│   │   └── db.json
│   └── Dockerfile            # Custom container image (optional)
└── task_files/               # Per-task file bundles (optional)
    ├── task_001/
    │   ├── run_script.sh
    │   └── parser.py
    └── task_002/
        └── config.yaml
```

## seed.py

Prepares the container before the agent starts working. Called once per task.

### Signature (MUST be async)

```python
async def seed(seed_args, container):
    """Prepare container state.
    
    Args:
        seed_args: dict from task's "seed_args" field in tasks.json
        container: Container object with exec/read/write methods
    """
```

### Container API in seed.py

```python
# Execute a command (returns tuple)
exit_code, output = await container.exec("bash /tmp/setup.sh", timeout=300)

# Read a file from container (returns str)
content = await container.read("/data/config.json")

# Write a file to container (takes bytes)
await container.write("/data/db.json", json.dumps(data).encode())

# Start a companion container (for tasks needing server processes)
await container.start_companion(image="my-server:latest", hostname="server", memory="512m")
```

### Common Patterns

**Reset repository to specific commit:**
```python
async def seed(seed_args, container):
    commit = seed_args["base_commit"]
    await container.exec(f"cd /app && git reset --hard {commit} && git clean -fdx", timeout=60)
    await container.write("/app/problem_statement.md", seed_args["problem_statement"].encode())
```

**Load database and scenario:**
```python
import json
from pathlib import Path

async def seed(seed_args, container):
    db_path = Path(__file__).parent / "data" / "db.json"
    await container.write("/data/db.json", db_path.read_bytes())
    await container.write("/data/scenario.json", json.dumps(seed_args.get("scenario", {})).encode())
```

**Start companion containers:**
```python
async def seed(seed_args, container):
    for companion in seed_args.get("companions", []):
        await container.start_companion(
            image=companion["image"],
            hostname=companion["hostname"],
            memory=companion.get("memory", "512m")
        )
    # Now the agent can reach companion at http://hostname:port
```

## verify.py

Evaluates the agent's work after it finishes. Called once per task.

### Signature (MUST be async)

```python
async def verify(expected_outcome, agent_answer, ctx):
    """Verify agent's work.
    
    Args:
        expected_outcome: dict from task's "expected_outcome" field in tasks.json
        agent_answer: str — the agent's final text response (often empty for agentic tasks)
        ctx: Container object (same API as seed's container — exec/read/write)
    
    Returns:
        dict with keys:
            is_correct: bool — whether the task was completed successfully
            reasoning: str — explanation of the verdict
            metrics: dict — optional numeric metrics (e.g., {"score": 0.75})
    """
```

### Return Value

```python
return {
    "is_correct": True,  # Required
    "reasoning": "All tests pass.\n✓ test_login\n✓ test_signup",  # Required
    "metrics": {"pass_rate": 1.0, "tests_passed": 5}  # Optional
}
```

### Common Patterns

**Run tests and parse results:**
```python
async def verify(expected_outcome, agent_answer, ctx):
    exit_code, output = await ctx.exec("cd /app && pytest tests/ -v", timeout=300)
    
    tests_passed = output.count("PASSED")
    tests_failed = output.count("FAILED")
    
    return {
        "is_correct": tests_failed == 0,
        "reasoning": f"Tests: {tests_passed} passed, {tests_failed} failed",
        "metrics": {"pass_rate": tests_passed / max(tests_passed + tests_failed, 1)}
    }
```

**Compare database state (τ²-bench pattern):**
```python
import json

async def verify(expected_outcome, agent_answer, ctx):
    actual_db = json.loads(await ctx.read("/data/db.json"))
    original_db = json.loads(await ctx.read("/data/db_original.json"))
    
    # Replay expected actions on original to get expected state
    expected_db = replay_actions(original_db, expected_outcome["actions"])
    
    if actual_db == expected_db:
        return {"is_correct": True, "reasoning": "DB state matches", "metrics": {"score": 1.0}}
    else:
        return {"is_correct": False, "reasoning": "DB state mismatch", "metrics": {"score": 0.0}}
```

**Check flag capture (CTF pattern):**
```python
async def verify(expected_outcome, agent_answer, ctx):
    try:
        flag = (await ctx.read("/tmp/flag.txt")).strip()
    except Exception:
        return {"is_correct": False, "reasoning": "No flag file found", "metrics": {}}
    
    expected = expected_outcome["flag"]
    correct = flag == expected
    return {
        "is_correct": correct,
        "reasoning": f"Flag: {flag} ({'matches' if correct else 'does not match'} expected)",
        "metrics": {}
    }
```

## Custom Tools

Each custom tool is a single Python file in `environment/tools/`.

### File Structure

```python
"""Short description of what this tool does."""

import json

# Required: tool schema (OpenAI function-calling format)
TOOL = {
    "name": "tool_name",
    "description": "What this tool does — shown to the agent.",
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "Description of param1"},
            "param2": {"type": "integer", "description": "Description of param2"}
        },
        "required": ["param1"]
    }
}

# Optional: context requirements (resolved from vivarium's namespaced pool)
CONTEXT = {
    "model_url": "run.model_url",    # The LLM API URL
    "model_key": "run.model_key",    # The LLM API key
    "model_name": "run.model_name",  # The model name being evaluated
}

# Required: execution function (SYNC — not async!)
def execute(args, container, context):
    """Execute the tool.
    
    Args:
        args: dict of parameter values from the agent's tool call
        container: Container object (sync API: container.read(), container.write(), container.exec_sync())
        context: dict of resolved CONTEXT values (empty dict if no CONTEXT defined)
    
    Returns:
        {"content": "result string"} on success
        {"error": "error message"} on failure
    """
    data = json.loads(container.read("/data/db.json"))
    result = data.get(args["param1"])
    if result is None:
        return {"error": f"Not found: {args['param1']}"}
    return {"content": json.dumps(result, indent=2)}
```

### Important: Sync Container API in Tools

In custom tools, the container API is **synchronous** (unlike seed/verify which are async):

```python
# In tools (SYNC):
content = container.read("/path")          # returns str
container.write("/path", b"bytes")         # takes bytes
exit_code, output = container.exec_sync("cmd", timeout=30)  # sync exec

# In seed.py/verify.py (ASYNC):
content = await container.read("/path")
await container.write("/path", b"bytes")
exit_code, output = await container.exec("cmd", timeout=30)
```

### Tool with LLM Access (User Simulator)

Use CONTEXT to get model credentials for tools that need to call an LLM (e.g., simulating a user in conversational benchmarks):

```python
CONTEXT = {
    "model_url": "run.model_url",
    "model_key": "run.model_key",
    "model_name": "run.model_name",
}

def execute(args, container, context):
    from openai import OpenAI
    client = OpenAI(base_url=context["model_url"], api_key=context["model_key"])
    response = client.chat.completions.create(
        model=context["model_name"],
        messages=[{"role": "user", "content": args["message"]}],
        max_tokens=500,
    )
    return {"content": response.choices[0].message.content}
```

### Registering Custom Tools

In info.json `env` config:

```json
{
  "env": {
    "default": {
      "tools": [],
      "custom_tools": ["tools/query_db.py", "tools/send_email.py"]
    }
  }
}
```

Set `"tools": []` (empty) if you ONLY want custom tools. Otherwise combine built-in + custom:
```json
"tools": ["bash", "read", "write"],
"custom_tools": ["tools/my_tool.py"]
```

## Multi-Environment Tasklists

When different tasks need different Docker images (e.g., SWE-bench Pro with per-repo images):

### info.json

```json
{
  "env": {
    "python-django": {"image": "swe-images:django", "tools": ["bash", "read", "write", "edit"]},
    "python-flask": {"image": "swe-images:flask", "tools": ["bash", "read", "write", "edit"]},
    "js-express": {"image": "swe-images:express", "tools": ["bash", "read", "write", "edit"]}
  }
}
```

### tasks.json (each task specifies its env)

```json
[
  {"id": "task_1", "objective": "...", "env": "python-django", "seed_args": {...}},
  {"id": "task_2", "objective": "...", "env": "python-flask", "seed_args": {...}},
  {"id": "task_3", "objective": "...", "env": "js-express", "seed_args": {...}}
]
```

**Key behavior**: Vivarium uses lazy spec registration — images are pulled only when a task first uses that environment. This enables tasklists with hundreds of unique images without blocking on pulling all of them upfront.

## task_files/ Directory

For per-task file bundles that get uploaded to the container:

1. Create `task_files/{attachment_id}/` with the files
2. Set `"attachment": "{attachment_id}"` in the task
3. Files land at `/task_files/` inside the container

```json
{"id": "task_001", "objective": "...", "attachment": "instance_repo_abc123", "seed_args": {...}}
```

In seed.py, reference these files:
```python
async def seed(seed_args, container):
    # Files from task_files/instance_repo_abc123/ are at /task_files/ in the container
    exit_code, _ = await container.exec("bash /task_files/run_script.sh", timeout=60)
```

## Dockerfile (Custom Image)

Place in `environment/Dockerfile`. Built automatically by vivarium when the spec is registered.

```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y python3 python3-pip git
WORKDIR /app
```

The entire `environment/` directory is sent as the build context (tar.gz archive) when registering the spec with vivarium.

**IMPORTANT**: If you reference a custom image name in info.json (e.g., `"image": "cybench-base"`), you MUST either:
1. Include a `Dockerfile` in `environment/` so vivarium can build it (preferred — makes the tasklist self-contained), OR
2. Use a publicly available image from Docker Hub (e.g., `"image": "python:3.11-slim"`)

A tasklist that references a non-public, non-buildable image is broken — it cannot be run by anyone else. **Always make tasklists self-contained.**

### Dependency Consistency

**Critical**: The Dockerfile (or chosen base image) must install EVERYTHING that your scripts and agent will need at runtime. Audit your seed.py, verify.py, custom tools, and agent_instructions — every binary, package, or library they reference must be present in the image.

Common mistakes:
- seed.py calls `gcc` to compile a challenge binary, but the image doesn't have gcc
- agent_instructions promise tools like `gdb`, `objdump`, `radare2`, but they aren't installed
- verify.py imports a Python package (`requests`, `flask`) not in the image
- seed.py runs `npm install` but Node.js isn't in the image

**Checklist before finalizing your Dockerfile:**
1. Read seed.py — what commands does it `exec()`? What does it `import`?
2. Read verify.py — same questions
3. Read agent_instructions — what tools are promised to the agent?
4. Read custom tools — what do they import or shell out to?
5. Ensure ALL of the above are installed in the Dockerfile

Example: if seed.py compiles C code and the agent needs reverse engineering tools:
```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y \
    gcc gdb objdump strings file ltrace strace \
    python3 python3-pip radare2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
```

## Companion Containers

For tasks needing server processes (e.g., web servers, databases):

### In tasks.json seed_args:

```json
{
  "seed_args": {
    "companions": [
      {"image": "my-server:latest", "hostname": "webserver", "memory": "512m"},
      {"image": "postgres:15", "hostname": "db", "memory": "256m"}
    ]
  }
}
```

### In seed.py:

```python
async def seed(seed_args, container):
    for comp in seed_args.get("companions", []):
        await container.start_companion(
            image=comp["image"],
            hostname=comp["hostname"],
            memory=comp.get("memory", "512m")
        )
```

The agent can then reach companions by hostname (e.g., `curl http://webserver:8080`).
