"""Generate SWE-bench Verified tasklist in palace format.

Requires: pip install swebench datasets

Usage:
    python create_dataset.py              # Full 500 tasks
    python create_dataset.py --limit 5    # PoC with 5 tasks
"""

import argparse
import json
import shutil
from pathlib import Path

from datasets import load_dataset
from swebench.harness.test_spec.python import (
    MAP_REPO_VERSION_TO_SPECS,
    make_env_script_list_py,
    make_eval_script_list_py,
    make_repo_script_list_py,
)

from platformdirs import user_cache_dir

TASKLISTS_PATH = Path(user_cache_dir("palace")) / "tasklists"
OUTPUT_DIR = TASKLISTS_PATH / "SWE-bench-Verified"
ENV_DIR = Path(__file__).parent  # seed.py, verify.py, Dockerfile are alongside this script


def generate_task(instance: dict) -> dict:
    """Convert a SWE-bench instance to a palace task dict."""
    repo = instance["repo"]
    version = instance["version"]
    base_commit = instance["base_commit"]
    test_patch = instance["test_patch"]

    specs = MAP_REPO_VERSION_TO_SPECS[repo][version]
    env_name = "testbed"
    repo_dir = "/testbed"

    env_scripts = make_env_script_list_py(instance, specs, env_name)
    repo_scripts = make_repo_script_list_py(specs, repo, repo_dir, base_commit, env_name)
    eval_scripts = make_eval_script_list_py(
        instance, specs, env_name, repo_dir, base_commit, test_patch
    )

    setup_script = "#!/bin/bash\nset -e\n" + "\n".join(env_scripts + repo_scripts)
    eval_script = "#!/bin/bash\n" + "\n".join(eval_scripts)
    # swebench uses `: 'marker'` (silent no-op) — replace with echo so we can parse output
    eval_script = eval_script.replace(": '>>>>> Start Test Output'", "echo '>>>>> Start Test Output'")
    eval_script = eval_script.replace(": '>>>>> End Test Output'", "echo '>>>>> End Test Output'")

    # Parse FAIL_TO_PASS and PASS_TO_PASS from the instance
    fail_to_pass = json.loads(instance["FAIL_TO_PASS"])
    pass_to_pass = json.loads(instance["PASS_TO_PASS"])

    objective = (
        f"Fix the following issue in the repository at /testbed/.\n\n"
        f"{instance['problem_statement']}\n\n"
        f"The repository is already cloned and the package is installed in editable mode. "
        f"Edit the source code to fix the issue. Your changes will be tested automatically."
    )

    return {
        "id": instance["instance_id"],
        "objective": objective,
        "seed_args": {
            "setup_script": setup_script,
            "problem_statement": instance["problem_statement"],
        },
        "expected_outcome": {
            "eval_script": eval_script,
            "fail_to_pass": fail_to_pass,
            "pass_to_pass": pass_to_pass,
            "repo": repo,
            "instance_id": instance["instance_id"],
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Generate SWE-bench Verified palace tasklist")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tasks")
    args = parser.parse_args()

    print("Loading SWE-bench Verified dataset...")
    ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")

    if args.limit:
        ds = ds.select(range(min(args.limit, len(ds))))
        print(f"Limited to {len(ds)} tasks")

    # Generate tasks
    tasks = []
    errors = []
    for i, instance in enumerate(ds):
        try:
            task = generate_task(instance)
            tasks.append(task)
        except Exception as e:
            errors.append((instance["instance_id"], str(e)))
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(ds)} instances ({len(errors)} errors)")

    print(f"Generated {len(tasks)} tasks ({len(errors)} errors)")
    if errors:
        print("Errors:")
        for iid, err in errors[:10]:
            print(f"  {iid}: {err}")

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # info.json
    info = {
        "name": "SWE-bench-Verified",
        "task_type": "Agentic",
        "category": "Agentic",
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "environment": {
            "tools": ["bash", "read", "write", "edit", "grep", "glob", "ls"],
            "image": "vivarium-env-swebench",
            "resources": {"memory": "4g", "cpus": 2.0, "network": True},
        },
    }
    (OUTPUT_DIR / "info.json").write_text(json.dumps(info, indent=2))

    # tasks.json
    (OUTPUT_DIR / "tasks.json").write_text(json.dumps(tasks, indent=2))

    # Copy environment files
    env_out = OUTPUT_DIR / "environment"
    env_out.mkdir(exist_ok=True)
    for fname in ["seed.py", "verify.py", "Dockerfile"]:
        src = ENV_DIR / fname
        if src.exists():
            shutil.copy2(src, env_out / fname)

    print(f"\nOutput written to: {OUTPUT_DIR}")
    print(f"  info.json: {(OUTPUT_DIR / 'info.json').stat().st_size} bytes")
    print(f"  tasks.json: {(OUTPUT_DIR / 'tasks.json').stat().st_size} bytes")
    print(f"  environment/: {list(env_out.iterdir())}")


if __name__ == "__main__":
    main()
