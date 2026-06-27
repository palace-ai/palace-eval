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

    # Agentic: check image is self-contained
    if task_type == "Agentic" and "env" in info:
        public_prefixes = ("python:", "ubuntu:", "debian:", "alpine:", "node:", "golang:", "rust:", "fedora:", "centos:")
        for env_name, env_spec in info["env"].items():
            img = env_spec.get("image", "")
            if not img:
                continue  # No image = uses vivarium default
            is_public = any(img.startswith(p) for p in public_prefixes) or "/" in img
            if is_public:
                continue
            env_path = env_spec.get("path", "environment")
            env_dir = tasklist_path / env_path
            has_dockerfile = env_dir.is_dir() and (env_dir / "Dockerfile").exists()
            if not has_dockerfile:
                warn(f"env '{env_name}' uses custom image '{img}' but no Dockerfile in {env_path}/ — tasklist may not be self-contained")

    # Classification should have task_type_fields.labels
    if task_type == "Classification":
        ttf = info.get("task_type_fields", {})
        if "labels" not in ttf:
            warn("Classification info.json has no task_type_fields.labels (tasks must provide per-task overrides)")

    # 2. Tasks — support both tasks.json and tasks_path glob
    tasks_path_pattern = info.get("tasks_path")
    if tasks_path_pattern:
        task_files = sorted(tasklist_path.glob(tasks_path_pattern))
        if not task_files:
            return error(f"No task files found matching tasks_path: '{tasks_path_pattern}'")
        tasks = []
        for tf in task_files:
            try:
                with open(tf) as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                passed = error(f"{tf.relative_to(tasklist_path)} is invalid JSON: {e}") and passed
                continue
            if isinstance(data, list):
                tasks.extend(data)
            elif isinstance(data, dict):
                tasks.append(data)
            else:
                passed = error(f"{tf.relative_to(tasklist_path)} must be a JSON array or object") and passed
        ok(f"tasks_path '{tasks_path_pattern}': {len(tasks)} tasks from {len(task_files)} file(s)")
    else:
        tasks_file = tasklist_path / "tasks.json"
        if not tasks_file.exists():
            return error("tasks.json not found (and no tasks_path in info.json)")
        try:
            with open(tasks_file) as f:
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
        # Collect all unique env paths to validate
        env_paths = {}
        if "env" in info:
            for env_name, env_spec in info["env"].items():
                env_paths[env_name] = env_spec.get("path", "environment")
        else:
            env_paths["default"] = "environment"

        for env_name, env_path in env_paths.items():
            env_dir = tasklist_path / env_path
            if not env_dir.is_dir():
                passed = error(f"Agentic env '{env_name}' missing {env_path}/ directory") and passed
                continue

            ok(f"{env_path}/ directory exists")

            # seed.py
            seed_path = env_dir / "seed.py"
            if not seed_path.exists():
                warn(f"{env_path}/seed.py not found (optional but common)")
            else:
                if not _check_async_function(seed_path, "seed"):
                    passed = error(f"{env_path}/seed.py must define 'async def seed(seed_args, container)'") and passed
                else:
                    ok(f"{env_path}/seed.py has correct async signature")

            # verify.py
            verify_path = env_dir / "verify.py"
            if not verify_path.exists():
                passed = error(f"Agentic env '{env_name}' missing {env_path}/verify.py") and passed
            else:
                if not _check_async_function(verify_path, "verify"):
                    passed = error(f"{env_path}/verify.py must define 'async def verify(expected_outcome, agent_answer, ctx)'") and passed
                else:
                    ok(f"{env_path}/verify.py has correct async signature")

            # Custom tools
            tools_dir = env_dir / "tools"
            if tools_dir.exists():
                for tool_file in sorted(tools_dir.glob("*.py")):
                    if not _check_async_function(tool_file, "execute"):
                        passed = error(f"{env_path}/tools/{tool_file.name} must define 'async def execute(args, context)'") and passed
                    else:
                        ok(f"{env_path}/tools/{tool_file.name} has correct async signature")

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
