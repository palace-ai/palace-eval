"""Pipeline stage functions for task evaluation."""

import logging
import time
from pathlib import Path
from typing import Any

from palace.agents.base_agent import Agent
from palace.analyzers.base import Analyzer
from palace.evaluation.renderers import Renderer
from palace.evaluation.types import AgentResult, PreparedTask, TaskResult
from palace.task_types.base import ExecutionEnvironment, Task, TaskVerificationResult
from palace.utils.exceptions import ConvergenceError
from palace.utils.io_adapters import IOAdapter
from palace.utils.multimodal import is_image_attachment
from palace.utils.printing import loading, print

_logger = logging.getLogger("palace.pipeline")


def prepare_prompt(task: Task, adapter: "IOAdapter | None", tasklist_path: Path) -> PreparedTask:
    """Resolve attachments, apply adapter, build final prompt."""
    image_path = None
    attachment_content = ""

    if task.attachment is not None and task.attachment != "":
        attachment_file = tasklist_path / "task_files" / task.attachment

        if is_image_attachment(task.attachment):
            image_path = str(attachment_file)
        else:
            try:
                with open(attachment_file, encoding="utf-8") as f:
                    attachment_content = f.read()
            except UnicodeDecodeError:
                return PreparedTask(prompt="", image=None, attachment_content="__UNSUPPORTED__")

            max_len = 200000
            if len(attachment_content) > max_len:
                attachment_content = attachment_content[:max_len]

    if adapter is not None:
        prompt = adapter.adapt_input(task, attachment_content)
    else:
        prompt = task.create_prompt()
        if attachment_content:
            prompt = f"Start of text attachment >>>\n{attachment_content}\n<<< End of text attachment\n\n{prompt}"

    return PreparedTask(prompt=prompt, image=image_path, attachment_content=attachment_content)


async def run_agent(agent: Agent, prepared: PreparedTask, task_id: str) -> AgentResult:
    """Call agent.run() with error handling."""
    start = time.time()
    try:
        result = await agent.run(prompt=prepared.prompt, image=prepared.image, task_id=task_id)
        result.elapsed = time.time() - start
        return result
    except ConvergenceError:
        return AgentResult(is_skipped=True, skip_reason="no_response", elapsed=time.time() - start)
    except Exception as e:
        _logger.warning(f"Agent error on task {task_id}: {e}")
        return AgentResult(is_skipped=True, skip_reason="agent_error", elapsed=time.time() - start)


async def verify_answer(
    task: Task, answer: str, env: ExecutionEnvironment | None, adapter: "IOAdapter | None"
) -> TaskVerificationResult:
    """Run verification (judge, custom verificator, or skip)."""
    # Apply output adapter
    if adapter is not None:
        answer = adapter.adapt_output(answer)

    # Custom verificator (exec'd Python code)
    if task.custom_verificator is not None and task.custom_verificator != "":
        try:
            local_env: dict = {}
            exec(task.custom_verificator, {}, local_env)
            verificator = local_env["verify"]
            is_correct = verificator(answer, task.expected)
            return TaskVerificationResult(is_correct=is_correct, reasoning=None)
        except Exception as e:
            _logger.warning(f"Custom verificator error on task {task.id}: {e}")
            return TaskVerificationResult(is_correct=False, is_skipped=True, skip_reason="custom_verificator_error", reasoning=str(e))

    # Standard verification via task type
    vr = await task.verify(answer, env=env)

    # Handle legacy tuple return
    if isinstance(vr, TaskVerificationResult):
        return vr
    else:
        is_correct, reasoning = vr
        return TaskVerificationResult(is_correct=is_correct, reasoning=reasoning)


async def run_analyzers(
    task: Task, answer: str, vr: TaskVerificationResult, analyzers: list[Analyzer], verbose: bool = False
) -> dict[str, Any]:
    """Run applicable analyzers and return metrics."""
    metrics: dict[str, Any] = {}
    for analyzer in analyzers:
        if type(task) not in analyzer.supported_task_types:
            continue
        try:
            if verbose:
                with loading() as ld:
                    ld.description = f"Running {analyzer.name}..."
                    result = await analyzer.analyze(task, answer, vr)
            else:
                result = await analyzer.analyze(task, answer, vr)
            metrics[analyzer.name] = result
            if verbose:
                print(analyzer.format_summary(result), box=True, box_title=f":mag: {analyzer.name}")
        except Exception as e:
            if verbose:
                print(f"[bold red]Analyzer {analyzer.name} failed: {e}[/]")
            metrics[analyzer.name] = {"error": str(e)}
    return metrics


def build_report(
    task: Task,
    agent_result: AgentResult,
    vr: TaskVerificationResult,
    analyzer_metrics: dict[str, Any],
    detail: str,
) -> dict[str, Any]:
    """Assemble the report entry dict."""
    entry: dict[str, Any] = {
        "actual": agent_result.answer,
        "is_correct": vr.is_correct,
        "is_skipped": vr.is_skipped,
        "skip_reason": vr.skip_reason,
        "reasoning": vr.reasoning,
        "elapsed_time": round(agent_result.elapsed, 2),
    }
    if detail == "full":
        entry["objective"] = task.objective
        entry["expected"] = task.expected_display()
    if vr.metrics:
        entry["metrics"] = vr.metrics
    if analyzer_metrics:
        entry.setdefault("metrics", {})["analyzers"] = analyzer_metrics
    if agent_result.metrics:
        for k, v in agent_result.metrics.items():
            entry[k] = v
    return entry


async def execute_task(
    i: int,
    task: Task,
    agent: Agent,
    adapter: "IOAdapter | None",
    tasklist_path: Path,
    analyzers: list[Analyzer],
    detail: str,
    renderer: Renderer,
) -> TaskResult:
    """Run one task through the full pipeline with lifecycle hooks."""
    env = await agent.on_task_start(task)

    try:
        # Prepare
        prepared = prepare_prompt(task, adapter, tasklist_path)

        # Handle unsupported attachment
        if prepared.attachment_content == "__UNSUPPORTED__":
            vr = TaskVerificationResult(is_correct=False, is_skipped=True, skip_reason="unsupported_attachment")
            entry = build_report(task, AgentResult(is_skipped=True, skip_reason="unsupported_attachment"), vr, {}, detail)
            return TaskResult(task.id, entry, vr)

        renderer.on_task_started(i, task, prepared.prompt)

        # Run agent
        renderer.on_agent_started(i)
        agent_result = await run_agent(agent, prepared, task.id)
        renderer.on_agent_finished(i, agent_result)

        # Verify
        if agent_result.answer is not None and not agent_result.is_skipped:
            renderer.on_verify_started(i)
            vr = await verify_answer(task, agent_result.answer, env, adapter)
            renderer.on_verify_finished(i, vr)
        else:
            vr = TaskVerificationResult(
                is_correct=False, is_skipped=True,
                skip_reason=agent_result.skip_reason or "no_response"
            )

        # Analyze
        analyzer_metrics: dict[str, Any] = {}
        if agent_result.answer and not vr.is_skipped:
            analyzer_metrics = await run_analyzers(task, agent_result.answer, vr, analyzers,
                                                   verbose=renderer.verbose)

        # Report
        report_entry = build_report(task, agent_result, vr, analyzer_metrics, detail)
        result = TaskResult(task.id, report_entry, vr)
        renderer.on_task_finished(i, result)
        return result

    finally:
        await agent.on_task_end(task)
