"""Seed: prepare container with repository at base_commit."""


async def seed(seed_args, container):
    """Write and execute the pre-generated setup script."""
    setup_script = seed_args["setup_script"]
    problem_statement = seed_args["problem_statement"]

    # Write setup script and execute
    await container.write("/tmp/setup.sh", setup_script.encode())
    exit_code, output = await container.exec("bash /tmp/setup.sh", timeout=900)
    if exit_code != 0:
        raise RuntimeError(
            f"Seed failed (exit {exit_code}):\n{output[-2000:]}"
        )

    # Make testbed python the default by prepending to PATH via /etc/bash.env
    # BASH_ENV is sourced by non-interactive bash (i.e. bash -c "...")
    exit_code, _ = await container.exec(
        "echo 'export PATH=/opt/miniconda3/envs/testbed/bin:$PATH' > /etc/bash.env",
        timeout=5,
    )
    if exit_code != 0:
        raise RuntimeError("Failed to write /etc/bash.env for conda PATH activation")

    # Write problem statement for agent reference
    await container.write("/testbed/problem_statement.md", problem_statement.encode())
