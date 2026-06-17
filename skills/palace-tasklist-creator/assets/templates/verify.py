"""Verify: check the agent's work after it finishes."""


async def verify(expected_outcome, agent_answer, ctx):
    """Evaluate whether the agent completed the task correctly.

    Args:
        expected_outcome: dict from the task's "expected_outcome" field in tasks.json
        agent_answer: str — the agent's final text response (often empty for agentic tasks)
        ctx: Container object with async exec/read/write methods

    Returns:
        dict with:
            is_correct: bool — whether the task was completed successfully
            reasoning: str — explanation of the verdict
            metrics: dict — optional numeric metrics
    """
    test_cmd = expected_outcome["test_command"]
    exit_code, output = await ctx.exec(test_cmd, timeout=120)

    passed = exit_code == 0
    return {
        "is_correct": passed,
        "reasoning": f"Tests {'PASSED' if passed else 'FAILED'} (exit code {exit_code}):\n{output[-1000:]}",
        "metrics": {"exit_code": exit_code},
    }
