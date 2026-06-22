"""Task dispatch with bounded concurrency."""

import asyncio
from pathlib import Path
from typing import Callable

from palace.agents.base_agent import Agent
from palace.analyzers.base import Analyzer
from palace.evaluation.pipeline import execute_task
from palace.evaluation.renderers import Renderer
from palace.evaluation.types import TaskResult
from palace.task_types.base import Task
from palace.utils.io_adapters import IOAdapter
from palace.utils.printing import print


async def dispatch_tasks(
    tasks: list[Task],
    agent: Agent,
    adapter: IOAdapter | None,
    tasklist_path: Path,
    tasklist_info: dict,
    task_files_dirs: list[Path],
    analyzers: list[Analyzer],
    concurrency: int,
    detail: str,
    renderer: Renderer,
    on_task_complete: Callable[[int, int], None] | None,
) -> list[TaskResult]:
    """Dispatch all tasks with bounded concurrency. Single path for all values."""
    await agent.on_tasklist_start(tasklist_path, tasklist_info)

    renderer.on_dispatch_start()

    sem = asyncio.Semaphore(concurrency)
    total = len(tasks)
    completed_count = 0

    ticker = renderer.start_ticker()

    async def bounded(i: int, task: Task) -> TaskResult:
        nonlocal completed_count
        async with sem:
            try:
                result = await execute_task(
                    i, task, agent, adapter, tasklist_path, task_files_dirs, analyzers, detail, renderer
                )
            except Exception as e:
                from palace.task_types.base import TaskVerificationResult
                error_msg = str(e) or type(e).__name__
                vr = TaskVerificationResult(is_correct=False, is_skipped=True, skip_reason=f"task_error: {error_msg}")
                entry = {
                    "actual": None, "is_correct": False, "is_skipped": True,
                    "skip_reason": f"task_error: {error_msg}", "reasoning": error_msg, "elapsed_time": 0.0,
                }
                result = TaskResult(task.id, entry, vr)
                renderer.on_task_finished(i, result)

            completed_count += 1
            if on_task_complete:
                on_task_complete(completed_count, total)
            return result

    try:
        results = await asyncio.gather(*[bounded(i, t) for i, t in enumerate(tasks)])
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n\n⚠ Interrupted — cleaning up...")
        raise
    finally:
        if ticker:
            ticker.cancel()
        renderer.on_all_finished()
        await agent.on_tasklist_end()

    return list(results)
