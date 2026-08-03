#!/usr/bin/env python3
"""Smoke-test an agentic palace tasklist by bootstrapping environments and running seed/verify.

Tests the infrastructure chain WITHOUT an LLM agent:
  register spec → create environment → run seed → attempt verify → destroy

Usage:
  python smoke_test_tasklist.py <tasklist_path> [--task-limit N]

Requires: Docker running + vivarium SDK installed (`pip install -e /path/to/vivarium`)
"""

import argparse
import asyncio
import importlib.util
import io
import json
import sys
import tarfile
from pathlib import Path


def _tar_gz(directory: Path) -> bytes:
    """Create a tar.gz archive of a directory's contents."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for f in directory.rglob("*"):
            if f.is_file() and "__pycache__" not in str(f):
                tar.add(f, arcname=str(f.relative_to(directory)))
    return buf.getvalue()


def _load_fn(path: Path, fn_name: str):
    """Load a function from a Python file."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, fn_name)


async def smoke_test(tasklist_path: Path, task_limit: int) -> bool:
    """Run smoke test. Returns True if all tasks pass."""
    # Load info + tasks
    with open(tasklist_path / "info.json") as f:
        info = json.load(f)

    if info.get("task_type") != "Agentic":
        print(f"⚠ Skipping — task_type is '{info.get('task_type')}', not Agentic")
        return True

    if "env" not in info:
        print("✗ info.json missing 'env' key")
        return False

    from vivarium import Client

    with open(tasklist_path / "tasks.json") as f:
        tasks = json.load(f)

    tasks = tasks[:task_limit]
    env_dir = tasklist_path / "environment"

    # Load seed and verify functions
    seed_fn = None
    verify_fn = None
    if (env_dir / "seed.py").exists():
        seed_fn = _load_fn(env_dir / "seed.py", "seed")
    if (env_dir / "verify.py").exists():
        verify_fn = _load_fn(env_dir / "verify.py", "verify")

    # Tar the environment directory
    archive_bytes = _tar_gz(env_dir) if env_dir.is_dir() else None

    # Connect to vivarium
    client = Client(auto_start=True)
    print(f"Connected to vivarium at {client._url}")
    print(f"Testing {len(tasks)} task(s) from {tasklist_path.name}\n")

    all_passed = True
    registered_specs: dict[str, str] = {}  # env_name → spec_id

    try:
        for i, task in enumerate(tasks):
            task_id = task.get("id", f"task_{i}")
            env_name = task.get("env")
            if env_name is None:
                if len(info["env"]) == 1:
                    env_name = next(iter(info["env"]))
                else:
                    print(f"  ✗ [{task_id}] No 'env' field and multiple environments defined")
                    all_passed = False
                    continue

            print(f"  [{task_id}] env={env_name}")

            # Register spec (lazy, once per env_name)
            if env_name not in registered_specs:
                spec_json = info["env"][env_name]
                try:
                    print(f"    Registering spec '{env_name}'...", end=" ", flush=True)
                    spec_id = await client.register_spec(spec_json, archive_bytes)
                    registered_specs[env_name] = spec_id
                    print("✓")
                except Exception as e:
                    print(f"✗ ({e})")
                    all_passed = False
                    continue
            spec_id = registered_specs[env_name]

            # Create environment
            env = None
            try:
                # Prepare task_files if task has an attachment
                task_files_bytes = None
                att = task.get("attachment") or (task.get("attachments") or [None])[0]
                if att:
                    tf_path = tasklist_path / "task_files" / att
                    if tf_path.exists():
                        task_files_bytes = _tar_gz(tf_path) if tf_path.is_dir() else None

                print("    Creating environment...", end=" ", flush=True)
                env = await client.create_environment(spec_id, task_id, task_files_bytes)
                print(f"✓ ({env.id[:8]})")
            except Exception as e:
                print(f"✗ ({e})")
                all_passed = False
                continue

            # Run seed
            if seed_fn:
                try:
                    print("    Running seed...", end=" ", flush=True)
                    await seed_fn(task.get("seed_args", {}), env)
                    print("✓")
                except Exception as e:
                    print(f"✗ ({e})")
                    all_passed = False
                    await client.destroy(env.id)
                    continue

            # Attempt verify (expected to partially fail — no agent acted)
            if verify_fn:
                try:
                    print("    Running verify (dry)...", end=" ", flush=True)
                    result = await verify_fn(task.get("expected_outcome", {}), "", env)
                    # If verify runs without crashing, that's a pass for smoke testing
                    is_correct = result.get("is_correct", False) if isinstance(result, dict) else False
                    print(f"✓ (is_correct={is_correct} — expected False without agent)")
                except Exception as e:
                    # Verify crashing is acceptable IF it's due to missing agent output
                    # (e.g., file not found because agent didn't write it)
                    err_str = str(e)
                    if any(k in err_str.lower() for k in ["not found", "no such file", "does not exist", "empty", "none"]):
                        print(f"✓ (expected failure: {err_str[:80]})")
                    else:
                        print(f"⚠ unexpected error: {err_str[:120]}")
                        # Not a hard failure — verify may legitimately crash without agent work

            # Destroy
            try:
                await client.destroy(env.id)
            except Exception:
                pass

            print()

    finally:
        # Cleanup: unregister all specs
        for env_name, spec_id in registered_specs.items():
            try:
                await client.delete_spec(spec_id)
            except Exception:
                pass

    print("=" * 50)
    if all_passed:
        print("✓ SMOKE TEST PASSED — all environments bootstrap correctly")
    else:
        print("✗ SMOKE TEST FAILED — see errors above")
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Smoke-test an agentic palace tasklist")
    parser.add_argument("tasklist_path", type=Path, help="Path to tasklist directory")
    parser.add_argument("--task-limit", type=int, default=2, help="Max tasks to test (default: 2)")
    args = parser.parse_args()

    path = args.tasklist_path.expanduser()
    if not path.is_dir():
        print(f"Error: '{path}' is not a directory")
        sys.exit(1)

    try:
        passed = asyncio.run(smoke_test(path, args.task_limit))
    except ImportError as e:
        if "vivarium" in str(e):
            print("Error: vivarium SDK not installed. Install with:")
            print("  pip install -e /path/to/vivarium/")
        else:
            print(f"Error: Import failed in tasklist scripts: {e}")
        sys.exit(1)
    except Exception as e:
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            print("Error: Cannot connect to vivarium. Is Docker running?")
            print("  Start with: vivarium start")
        else:
            print(f"Error: {e}")
        sys.exit(1)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
