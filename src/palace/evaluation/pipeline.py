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
from typing import TYPE_CHECKING, Any

from palace.agents.base_agent import Agent
from palace.analyzers.base import Analyzer
from palace.evaluation.renderers import Renderer
from palace.evaluation.types import AgentResult, Attachment, PreparedTask, TaskResult
from palace.task_types.base import ExecutionEnvironment, Task, TaskVerificationResult
from palace.utils.exceptions import ConvergenceError, FatalEvaluationError
from palace.utils.io_adapters import IOAdapter
from palace.utils.multimodal import mime_from_extension
from palace.utils.printing import loading, print

if TYPE_CHECKING:
    from palace.evaluation.judge_config import JudgeConfig

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
    task: Task,
    answer: str,
    env: ExecutionEnvironment | None,
    adapter: "IOAdapter | None",
    judge_config: "JudgeConfig | None" = None,
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
    vr = await task.verify(answer, env=env, judge_config=judge_config)

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


def _rate(numerator: float | None, denominator: float | None) -> float | None:
    """Compute a tokens-per-second rate, or None when inputs are missing/zero."""
    if numerator is None or denominator is None or denominator <= 0 or numerator < 0:
        return None
    return round(numerator / denominator, 1)


def _ms_to_s(value: float | None) -> float | None:
    """Normalize a server-reported milliseconds value to seconds (lossless)."""
    if value is None:
        return None
    return round(value / 1000, 4)


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
    }
    if detail == "full":
        entry["objective"] = task.objective
        entry["expected"] = task.expected_display()
    if vr.metrics:
        entry["metrics"] = vr.metrics
    if analyzer_metrics:
        entry.setdefault("metrics", {})["analyzers"] = analyzer_metrics

    # Group agent metrics into the operational bucket, nested by metric type
    if agent_result.metrics:
        m = agent_result.metrics
        compute = m.get("compute_seconds")
        ttfc = m.get("ttfc_seconds")
        ttfcc = m.get("ttfcc_seconds")
        input_tokens = m.get("input_tokens")
        output_tokens = m.get("output_tokens")
        output_chunks = m.get("output_chunks")
        reasoning_chunks = m.get("reasoning_chunks")
        reasoning_tokens = m.get("reasoning_tokens")
        total_chunks = m.get("total_chunks")
        attempts = m.get("attempts")
        # Reasoning status: "streamed" (chunks on the wire), "hidden" (server
        # reports a count > 0, nothing streamed), "none" (known empty), or
        # None (unknown — endpoint reports neither).
        if reasoning_chunks:
            reasoning_status = "streamed"
        elif reasoning_tokens:
            reasoning_status = "hidden"
        elif reasoning_tokens == 0:
            reasoning_status = "none"
        else:
            reasoning_status = None
        # Client latency semantics depend on the reasoning regime:
        # - streamed: ttfc lands on the first reasoning chunk, emitted right
        #   after prefill -> good TTFT proxy; ttfcc is the exact content onset.
        # - absent: the first chunk IS the first content chunk -> ttfc is the
        #   authoritative TTFT and ttfcc == ttfc.
        # - hidden: ttfc absorbs the whole unobservable reasoning phase ->
        #   unreliable, report None. ttfcc is still exact (by definition of
        #   hidden, the first chunk delivered is the first content chunk).
        # - unknown: cannot certify which case applies -> both None.
        ttfc_reported = reasoning_status in ("streamed", "none")
        # Server-reported latency checkpoint, normalized (ms -> seconds) into
        # the fixed per-metric-type schema below. Any key the endpoint does
        # not provide stays None, so the JSON shape is identical everywhere.
        server_in = m.get("server_latency") or {}
        entry["operational"] = {
            "reasoning_status": reasoning_status,
            "timing": {
                # Client request duration: t0 to full stream consumption.
                "total_seconds": round(compute, 2) if compute is not None else None,
                # Whole agent run, including retry waits and failed attempts.
                "wall_seconds": round(agent_result.elapsed, 2),
                "ttfc_seconds": round(ttfc, 2) if ttfc is not None and ttfc_reported else None,
                "ttfcc_seconds": (
                    round(ttfcc, 2)
                    if ttfcc is not None and reasoning_status in ("streamed", "hidden", "none")
                    else None
                ),
                # Server-reported (authoritative when present), regime-independent.
                "server": {
                    "engine_ttft_seconds": _ms_to_s(server_in.get("engine_ttft_ms")),
                    "service_ttft_seconds": _ms_to_s(server_in.get("service_ttft_ms")),
                    "user_visible_ttft_seconds": _ms_to_s(server_in.get("user_visible_ttft_ms")),
                    "pre_inference_seconds": _ms_to_s(server_in.get("pre_inference_ms")),
                    "engine_tbt_seconds": _ms_to_s(server_in.get("engine_tbt_ms")),
                    "service_tbt_seconds": _ms_to_s(server_in.get("service_tbt_ms")),
                    "engine_ttlt_seconds": _ms_to_s(server_in.get("engine_ttlt_ms")),
                },
            },
            # Client-derived rates. Vocabulary: prefill = input, generation =
            # output (reasoning + content), total = prefill + generation.
            "throughput": {
                # Exact only when ttfc provably contains no generation time:
                # reasoning streamed or known-empty. Hidden or unknown reasoning
                # means ttfc silently absorbs reasoning time — report None.
                # Buffered delivery (<= 2 chunks) makes ttfc meaningless as a
                # phase boundary — report None.
                "prefill_cps": _rate(input_tokens, ttfc)
                if ttfc_reported and (output_chunks is None or output_chunks > 2)
                else None,
                # Output tokens over the full generation window (ttfc ->
                # stream end). Exact when the window provably covers all
                # generation: streamed (starts at the first reasoning token)
                # or absent (no reasoning). Null in hidden mode (the window
                # excludes the invisible reasoning time, so the rate would
                # overestimate); null in unknown mode (window start
                # uncertifiable).
                "generation_cps": _rate(output_tokens, compute - ttfc)
                if compute is not None
                and ttfc is not None
                and output_tokens is not None
                and reasoning_status in ("streamed", "none")
                and (output_chunks is None or output_chunks > 2)
                and (compute - ttfc) >= 1.0
                else None,
                # Content tokens over the content window (first content chunk
                # -> stream end). Numerator exact only when the reasoning
                # split is certified — streamed with a reported count, hidden
                # (by definition the split is reported), or none (count 0).
                # In streamed mode the window starts at ttfcc; in hidden mode
                # it starts at the first (content) chunk.
                "content_cps": (
                    _rate(
                        output_tokens - reasoning_tokens if reasoning_tokens is not None else output_tokens,
                        compute - ttfcc,
                    )
                    if compute is not None
                    and ttfcc is not None
                    and output_tokens is not None
                    and reasoning_tokens is not None
                    and (output_chunks is None or output_chunks > 2)
                    and (compute - ttfcc) >= 1.0
                    else None
                ),
                # Full-request rate: all tokens over t0 -> stream end. The only
                # client rate in unknown mode — but only when the token
                # accounting is certified (usage + a known reasoning regime);
                # an arbitrary gateway might exclude hidden reasoning tokens
                # from output_tokens, and in unknown mode we cannot tell.
                "total_cps": _rate(
                    input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None,
                    compute,
                )
                if reasoning_status is not None
                else None,
            },
            # Server-reported token counts, verbatim.
            "tokens": {
                "input_tokens": input_tokens,
                # All generated tokens, including hidden reasoning tokens.
                "output_tokens": output_tokens,
                # Server-reported subset generated as (hidden) reasoning.
                # null when the endpoint does not report it.
                "reasoning_tokens": reasoning_tokens,
            },
            # Client-observed delivery granularity.
            "chunks": {
                # Chunks carrying output (content or reasoning).
                "output_chunks": output_chunks,
                # Chunks carrying reasoning_content.
                "reasoning_chunks": reasoning_chunks,
                # All stream chunks, including role/usage-only frames — the
                # gateway buffering diagnostic (large gap vs output_chunks).
                "total_chunks": total_chunks,
            },
            # API attempts for this task's successful request (1 = no retry).
            # Exposed at the bucket root: it is a request-level fact, not a
            # timing/token/chunk measurement.
            "attempts": attempts,
        }
        # Copy any other metrics that aren't operational (e.g., vivarium's steps)
        for k, v in m.items():
            if k not in (
                "input_tokens",
                "output_tokens",
                "compute_seconds",
                "ttfc_seconds",
                "ttfcc_seconds",
                "output_chunks",
                "reasoning_chunks",
                "reasoning_tokens",
                "total_chunks",
                "server_latency",
                "attempts",
            ):
                entry[k] = v
    else:
        # No agent metrics — no request operation to describe; wall time only.
        entry["operational"] = {"timing": {"wall_seconds": round(agent_result.elapsed, 2)}}

    # Diagnostic: the agent run completed but produced no final text. Recorded
    # as an operational fact (not a verification reason) — answer-based task
    # types will naturally judge the empty answer incorrect; env-based types
    # grade the work in the environment regardless.
    if agent_result.answer is None and agent_result.outcome == "success":
        entry.setdefault("operational", {})["final_answer"] = False

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
    judge_config: "JudgeConfig | None" = None,
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
        # Gated on outcome, not on the answer: a completed agent run is always
        # verified. An empty answer (agent finished without final text) is a
        # valid verification input — answer-based task types judge it incorrect
        # through their normal path, env-based (agentic) types grade the work
        # in the environment and may still pass. Only error/unsupported runs
        # skip verification.
        if agent_result.outcome == "success":
            renderer.on_verify_started(i)
            verify_env = agent.get_verify_env(task) or env
            vr = await verify_answer(task, agent_result.answer or "", verify_env, adapter, judge_config)
            renderer.on_verify_finished(i, vr)
        else:
            vr = TaskVerificationResult(is_correct=False, outcome=agent_result.outcome, reason=agent_result.reason)

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
