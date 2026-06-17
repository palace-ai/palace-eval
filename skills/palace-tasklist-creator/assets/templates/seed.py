"""Seed: prepare container state before the agent runs."""


async def seed(seed_args, container):
    """Set up the container for this task.

    Args:
        seed_args: dict from the task's "seed_args" field in tasks.json
        container: Container object with async exec/read/write methods
    """
    # Write source files
    await container.write("/app/calculator.py", seed_args["bug_code"].encode())
    await container.write("/app/tests/test_calc.py", seed_args["test_code"].encode())

    # Install dependencies
    exit_code, output = await container.exec("pip install pytest", timeout=60)
    if exit_code != 0:
        raise RuntimeError(f"Setup failed: {output[-500:]}")
