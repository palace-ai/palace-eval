#!/usr/bin/env python3
"""Validate a palace tasklist directory for structural correctness.

Usage: python validate_tasklist.py <tasklist_path>

Checks:
- info.json exists and has required fields
- tasks.json exists and is a valid JSON array
- task_type is one of the 5 valid types
- Agentic: environment/ has seed.py and verify.py with async signatures
- Classification: labels consistency between info and tasks
- Attachments reference existing files in task_files/
"""

import ast
import json
import sys
from pathlib import Path

VALID_TASK_TYPES = {"QA", "Classification", "Criteria Evaluation", "Instruction Following", "Agentic"}


def error(msg):
    print(f"  ✗ {msg}")
    return False


def warn(msg):
    print(f"  ⚠ {msg}")


def ok(msg):
    print(f"  ✓ {msg}")


def validate(tasklist_path: Path) -> bool:
    """Validate a tasklist directory. Returns True if valid."""
    print(f"\nValidating: {tasklist_path.name}")
    print("=" * 50)
    passed = True

    # 1. info.json
    info_path = tasklist_path / "info.json"
    if not info_path.exists():
        return error("info.json not found")

    try:
        with open(info_path) as f:
            info = json.load(f)
    except json.JSONDecodeError as e:
        return error(f"info.json is invalid JSON: {e}")

    ok("info.json exists and is valid JSON")

    # Required fields
    if "name" not in info:
        passed = error("info.json missing 'name' field") and passed
    if "task_type" not in info:
        return error("info.json missing 'task_type' field")

    task_type = info["task_type"]
    if task_type not in VALID_TASK_TYPES:
        passed = error(f"Invalid task_type '{task_type}'. Must be one of: {VALID_TASK_TYPES}") and passed
    else:
        ok(f"task_type: {task_type}")

    # Agentic must have env
    if task_type == "Agentic" and "env" not in info:
        passed = error("Agentic tasklist must have 'env' key in info.json") and passed

    # Classification should have task_type_fields.labels
    if task_type == "Classification":
        ttf = info.get("task_type_fields", {})
        if "labels" not in ttf:
            warn("Classification info.json has no task_type_fields.labels (tasks must provide per-task overrides)")

    # 2. tasks.json
    tasks_path = tasklist_path / "tasks.json"
    if not tasks_path.exists():
        return error("tasks.json not found")

    try:
        with open(tasks_path) as f:
            tasks = json.load(f)
    except json.JSONDecodeError as e:
        return error(f"tasks.json is invalid JSON: {e}")

    if not isinstance(tasks, list):
        return error("tasks.json must be a JSON array")

    if len(tasks) == 0:
        passed = error("tasks.json is empty") and passed
    else:
        ok(f"tasks.json: {len(tasks)} tasks")

    # Check task fields
    ids_seen = set()
    for i, task in enumerate(tasks[:50]):  # Sample first 50
        if "id" not in task:
            passed = error(f"Task at index {i} missing 'id' field") and passed
        elif task["id"] in ids_seen:
            passed = error(f"Duplicate task id: '{task['id']}'") and passed
        else:
            ids_seen.add(task["id"])

        if "objective" not in task:
            passed = error(f"Task '{task.get('id', f'index {i}')}' missing 'objective' field") and passed

    # Check all IDs unique (full scan)
    all_ids = [t.get("id") for t in tasks if "id" in t]
    if len(all_ids) != len(set(all_ids)):
        passed = error("Duplicate task IDs found") and passed
    else:
        ok("All task IDs are unique")

    # 3. Agentic-specific checks
    if task_type == "Agentic":
        env_dir = tasklist_path / "environment"
        if not env_dir.is_dir():
            passed = error("Agentic tasklist missing environment/ directory") and passed
        else:
            ok("environment/ directory exists")

            # seed.py
            seed_path = env_dir / "seed.py"
            if not seed_path.exists():
                warn("environment/seed.py not found (optional but common)")
            else:
                if not _check_async_function(seed_path, "seed"):
                    passed = error("seed.py must define 'async def seed(seed_args, container)'") and passed
                else:
                    ok("seed.py has correct async signature")

            # verify.py
            verify_path = env_dir / "verify.py"
            if not verify_path.exists():
                passed = error("Agentic tasklist missing environment/verify.py") and passed
            else:
                if not _check_async_function(verify_path, "verify"):
                    passed = error("verify.py must define 'async def verify(expected_outcome, agent_answer, ctx)'") and passed
                else:
                    ok("verify.py has correct async signature")

        # Multi-env: check tasks have env field
        if "env" in info and len(info["env"]) > 1:
            missing_env = [t.get("id", f"idx-{i}") for i, t in enumerate(tasks) if "env" not in t]
            if missing_env:
                passed = error(f"Multi-env tasklist but {len(missing_env)} task(s) missing 'env' field") and passed
            else:
                ok("All tasks specify their environment")

            # Check env references are valid
            valid_envs = set(info["env"].keys())
            invalid_refs = [
                t.get("id") for t in tasks
                if "env" in t and t["env"] not in valid_envs
            ]
            if invalid_refs:
                passed = error(f"Tasks reference unknown environments: {invalid_refs[:5]}") and passed

    # 4. Attachment checks
    task_files_dir = tasklist_path / "task_files"
    has_attachments = any(
        t.get("attachment") or t.get("attachments") for t in tasks
    )
    if has_attachments and not task_files_dir.exists():
        # Only warn — some tasklists use inline attachments
        warn("Tasks reference attachments but task_files/ directory not found")
    elif has_attachments and task_files_dir.exists():
        # Sample check first 20 tasks
        missing = []
        for task in tasks[:20]:
            atts = task.get("attachments") or ([task["attachment"]] if task.get("attachment") else [])
            for att in atts:
                att_path = task_files_dir / att
                if not att_path.exists():
                    missing.append(att)
        if missing:
            warn(f"{len(missing)} attachment(s) not found in task_files/ (sampled first 20 tasks)")
        else:
            ok("Sampled attachments exist in task_files/")

    # 5. Classification label checks
    if task_type == "Classification":
        info_labels = info.get("task_type_fields", {}).get("labels", [])
        info_label_names = {l["name"] for l in info_labels}

        tasks_with_labels = [t for t in tasks if "labels" in t]
        if not tasks_with_labels:
            warn("No tasks have 'labels' field (required for Classification)")
        else:
            # Check label keys match info.json
            sample = tasks_with_labels[:20]
            for task in sample:
                task_label_names = set(task["labels"].keys())
                # Labels from task override or info level
                task_ttf_labels = task.get("task_type_fields", {}).get("labels", [])
                if task_ttf_labels:
                    expected_names = {l["name"] for l in task_ttf_labels}
                elif info_label_names:
                    expected_names = info_label_names
                else:
                    continue
                if not task_label_names.issubset(expected_names):
                    extra = task_label_names - expected_names
                    warn(f"Task '{task['id']}' has label keys {extra} not in task_type_fields")
                    break
            ok(f"Classification labels consistent (sampled {len(sample)} tasks)")

    # Summary
    print("\n" + "=" * 50)
    if passed:
        print("✓ VALID — tasklist is structurally correct")
    else:
        print("✗ INVALID — fix errors above")
    return passed


def _check_async_function(path: Path, func_name: str) -> bool:
    """Check if a file defines an async function with the given name."""
    try:
        source = path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == func_name:
                return True
    except SyntaxError:
        return False
    return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_tasklist.py <tasklist_path>")
        print("Example: python validate_tasklist.py ~/.cache/palace/tasklists/GuardBench-EN")
        sys.exit(1)

    path = Path(sys.argv[1]).expanduser()
    if not path.is_dir():
        print(f"Error: '{path}' is not a directory")
        sys.exit(1)

    valid = validate(path)
    sys.exit(0 if valid else 1)
