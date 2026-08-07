# Copyright (C) 2025 European Union
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the European Union Public Licence (EUPL) v. 1.2
# as published by the European Union.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# European Union Public Licence for more details.
#
# You should have received a copy of the European Union Public Licence
# along with this program. If not, see <https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12>.

"""Pipeline stage functions for task evaluation."""

import logging
import time
from pathlib import Path
from typing import Any

from palace.agents.base_agent import Agent
from palace.analyzers.base import Analyzer
from palace.evaluation.renderers import Renderer
from palace.evaluation.types import AgentResult, Attachment, PreparedTask, TaskResult
from palace.task_types.base import ExecutionEnvironment, Task, TaskVerificationResult
from palace.utils.exceptions import ConvergenceError, FatalEvaluationError
from palace.utils.io_adapters import IOAdapter
from palace.utils.multimodal import mime_from_extension
from palace.utils.printing import loading, print

_logger = logging.getLogger("palace.pipeline")

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".xml",
    ".html",
    ".yaml",
    ".yml",
    ".log",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".go",
    ".rs",
    ".sh",
    ".bash",
    ".sql",
    ".r",
    ".toml",
    ".ini",
    ".cfg",
}


def prepare_prompt(
    task: Task, adapter: "IOAdapter | None", tasklist_path: Path, task_files_dirs: "list[Path] | None" = None
) -> PreparedTask:
    """Resolve attachments and build prompt. Presentation is the agent's responsibility."""
    _dirs = task_files_dirs or [tasklist_path / "task_files"]

    attachments, error = _resolve_attachments(task, _dirs, tasklist_path)
    if error:
        return PreparedTask(prompt="", error=error)

    if adapter is not None:
        text_content = _get_text_content(attachments)
        prompt = adapter.adapt_input(task, text_content)
    else:
        prompt = task.create_prompt()

    return PreparedTask(prompt=prompt, attachments=attachments)


def _resolve_attachments(task: Task, dirs: "list[Path]", tasklist_path: Path) -> "tuple[list[Attachment], str | None]":
    """Find files and assign mime types. Returns (attachments, error_or_None)."""
    attachments: list[Attachment] = []
    for att in task.attachments:
        if not att:
            continue
        path = _find_file(att, dirs)
        if path is None:
            # Fallback check in default location
            fallback = tasklist_path / "task_files" / att
            if fallback.exists():
                path = fallback
            else:
                return [], "missing_attachment"
        ext = Path(att).suffix.lower()
        mime = "text/plain" if ext in TEXT_EXTENSIONS else mime_from_extension(ext)
        attachments.append(Attachment(path=str(path), mime_type=mime, filename=att))
    return attachments, None


def _find_file(filename: str, dirs: "list[Path]") -> "Path | None":
    """Search for a file in the given directories. Returns first match or None."""
    for d in dirs:
        candidate = d / filename
        if candidate.exists():
            return candidate
    return None


def _get_text_content(attachments: "list[Attachment]") -> str:
    """Extract text content from text attachments (for adapter template substitution)."""
    for att in attachments:
        text = att.read_text()
        if text is not None:
            return text
    return ""


async def run_agent(agent: Agent, prepared: PreparedTask, task_id: str) -> AgentResult:
    """Call agent.run() with error handling."""
    start = time.time()
    try:
        result = await agent.run(prompt=prepared.prompt, attachments=prepared.attachments or None, task_id=task_id)
        result.elapsed = time.time() - start
        return result
    except FatalEvaluationError:
        # Re-raise fatal errors that should abort the evaluation
        raise
    except ConvergenceError:
        return AgentResult(outcome="error", reason="no_response", elapsed=time.time() - start)
    except Exception as e:
        _logger.warning(f"Agent error on task {task_id}: {e}")
        return AgentResult(outcome="error", reason=f"agent_error: {e}", elapsed=time.time() - start)


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
            return TaskVerificationResult(
                is_correct=False, outcome="error", reason=f"custom_verificator_error: {e}", reasoning=str(e)
            )

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
        "outcome": vr.outcome,
        "is_skipped": vr.is_skipped,
        "skip_reason": vr.skip_reason,
        "reason": vr.reason,
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
    task_files_dirs: "list[Path] | None",
    analyzers: list[Analyzer],
    detail: str,
    renderer: Renderer,
) -> TaskResult:
    """Run one task through the full pipeline with lifecycle hooks."""
    renderer.on_init_started(i)
    env = None

    try:
        env = await agent.on_task_start(task)

        # Prepare
        prepared = prepare_prompt(task, adapter, tasklist_path, task_files_dirs)

        # Handle attachment resolution error
        if prepared.error:
            vr = TaskVerificationResult(is_correct=False, outcome="error", reason=prepared.error)
            entry = build_report(task, AgentResult(outcome="error", reason=prepared.error), vr, {}, detail)
            result = TaskResult(task.id, entry, vr)
            renderer.on_task_finished(i, result)
            return result

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
                is_correct=False, outcome=agent_result.outcome, reason=agent_result.reason or "no_response"
            )

        # Analyze
        analyzer_metrics: dict[str, Any] = {}
        if agent_result.answer and not vr.is_skipped:
            analyzer_metrics = await run_analyzers(task, agent_result.answer, vr, analyzers, verbose=renderer.verbose)

        # Report
        report_entry = build_report(task, agent_result, vr, analyzer_metrics, detail)
        result = TaskResult(task.id, report_entry, vr)
        renderer.on_task_finished(i, result)
        return result

    finally:
        await agent.on_task_end(task)
