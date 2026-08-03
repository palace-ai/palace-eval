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

"""Renderer protocol and implementations for evaluation output."""

import asyncio
import atexit
import os
import sys
import time
from collections import Counter
from datetime import datetime
from io import TextIOWrapper
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from palace.task_types.base import TaskVerificationResult
from palace.utils.printing import PersistentStatus, loading, print

if TYPE_CHECKING:
    from palace.evaluation.types import AgentResult, TaskResult
    from palace.task_types.base import Task


class Renderer(Protocol):
    """Protocol for evaluation output rendering."""

    verbose: bool

    def on_init_started(self, i: int) -> None: ...
    def on_task_started(self, i: int, task: "Task", prompt: str) -> None: ...
    def on_agent_started(self, i: int) -> None: ...
    def on_agent_finished(self, i: int, result: "AgentResult") -> None: ...
    def on_verify_started(self, i: int) -> None: ...
    def on_verify_finished(self, i: int, vr: TaskVerificationResult) -> None: ...
    def on_task_finished(self, i: int, result: "TaskResult") -> None: ...
    def on_all_finished(self) -> None: ...
    def on_dispatch_start(self) -> None: ...
    def start_ticker(self) -> "asyncio.Task | None": ...


class _LogMixin:
    """Mixin that adds file logging to any renderer."""

    _log: TextIOWrapper | None

    def _init_log(self, log_path: Path | None):
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log = open(log_path, "a", encoding="utf-8")
            atexit.register(self._close_log)
            # Also route palace.* loggers (e.g. retry warnings) to same file
            import logging

            logger = logging.getLogger("palace")
            logger.handlers = [h for h in logger.handlers if not isinstance(h, logging.FileHandler)]
            handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(message)s", datefmt="%H:%M:%S"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        else:
            self._log = None

    def _log_line(self, msg: str):
        if self._log:
            ts = datetime.now().strftime("%H:%M:%S")
            self._log.write(f"{ts} {msg}\n")
            self._log.flush()

    def _close_log(self):
        if self._log:
            self._log.close()


class VerboseRenderer(_LogMixin):
    """Rich output with boxes, spinners, and reasoning. For concurrency=1 + tty."""

    verbose = True

    def __init__(self, total: int, log_path: Path | None = None):
        self.total = total
        self._status = PersistentStatus()
        self._status.start()
        self._loop_start = time.time()
        self._completed = 0
        self._correct = 0
        self._skipped = 0
        self._loading_ctx = None
        self._init_log(log_path)

    def on_dispatch_start(self) -> None:
        pass

    def on_init_started(self, i: int) -> None:
        pass

    def start_ticker(self) -> "asyncio.Task | None":
        return None

    def on_task_started(self, i: int, task: "Task", prompt: str) -> None:
        if i > 0:
            failed = self._completed - self._correct - self._skipped
            elapsed = time.time() - self._loop_start
            eta = elapsed / i * (self.total - i)
            eta_str = f"{int(eta // 60)}m {int(eta % 60)}s" if eta >= 60 else f"{int(eta)}s"
            pct = i / self.total
            filled = int(pct * 20)
            bar = "█" * filled + "░" * (20 - filled)
            self._status.update(
                f"{bar} {i}/{self.total} | ✓ {self._correct} ✗ {failed} ⏭ {self._skipped} | ETA: {eta_str}"
            )
        else:
            self._status.update(f"{'░' * 20} 0/{self.total}")

        self._log_line(f"[{i + 1}/{self.total}] START task={task.id}")
        print()
        print(prompt, box=True, box_title=f":memo: Task {i + 1}/{self.total}")
        if task.expected_display() is not None:
            print(task.expected_display(), box=True, box_title=":fleur_de_lis: Expected Answer")

    def on_agent_started(self, i: int) -> None:
        self._loading_ctx = loading()
        ld = self._loading_ctx.__enter__()
        ld.description = "Agent generating response..."

    def on_agent_finished(self, i: int, result: "AgentResult") -> None:
        if self._loading_ctx is not None:
            self._loading_ctx.__exit__(None, None, None)
            self._loading_ctx = None
        if result.is_skipped:
            self._log_line(f"[{i + 1}/{self.total}] AGENT_SKIP reason={result.skip_reason}")
        else:
            self._log_line(f"[{i + 1}/{self.total}] AGENT_OK len={len(result.answer or '')}")
        if result.answer is not None:
            print(result.answer, box=True, box_title=":left_speech_bubble: Agent Answer")

    def on_verify_started(self, i: int) -> None:
        self._loading_ctx = loading()
        ld = self._loading_ctx.__enter__()
        ld.description = "Verifying answer..."

    def on_verify_finished(self, i: int, vr: TaskVerificationResult) -> None:
        if self._loading_ctx is not None:
            self._loading_ctx.__exit__(None, None, None)
            self._loading_ctx = None
        if vr.outcome == "unsupported":
            self._log_line(f"[{i + 1}/{self.total}] VERIFY unsupported={vr.reason}")
            print(f"[bold magenta]:prohibited: Unsupported: {vr.reason}[/]")
        elif vr.outcome == "error":
            self._log_line(f"[{i + 1}/{self.total}] VERIFY error={vr.reason}")
            print(f"[bold yellow]:warning: Error: {vr.reason}[/]")
        elif vr.is_correct:
            self._log_line(f"[{i + 1}/{self.total}] VERIFY correct=True")
            print("[bold green]:white_check_mark: Correct[/]")
        else:
            self._log_line(f"[{i + 1}/{self.total}] VERIFY correct=False")
            print("[bold red]:cross_mark: Incorrect[/]")
        if vr.reasoning is not None:
            print(vr.reasoning, box=True, box_title=":judge: Reasoning")

    def on_task_finished(self, i: int, result: "TaskResult") -> None:
        self._completed += 1
        if result.verification.is_skipped:
            self._skipped += 1
        elif result.verification.is_correct:
            self._correct += 1
        elapsed = result.report_entry.get("elapsed_time", 0)
        if result.verification.is_skipped:
            reason = result.verification.reason or "unknown"
            self._log_line(
                f"[{i + 1}/{self.total}] {result.verification.outcome.upper()} task={result.task_id} reason={reason} elapsed={elapsed:.1f}s"
            )
        else:
            self._log_line(f"[{i + 1}/{self.total}] DONE task={result.task_id} elapsed={elapsed:.1f}s")

    def on_all_finished(self) -> None:
        if self._loading_ctx is not None:
            self._loading_ctx.__exit__(None, None, None)
            self._loading_ctx = None
        self._status.stop()
        self._close_log()


class CompactRenderer(_LogMixin):
    """Progress bar with symbols and ETA. For concurrency>1 + tty."""

    verbose = False

    def __init__(self, total: int, concurrency: int, log_path: Path | None = None):
        self.total = total
        self.concurrency = concurrency
        self.completed = 0
        self.correct = 0
        self.failed = 0
        self.states = ["○"] * total
        self._start = time.monotonic()
        self._task_times: list[float] = []
        self._task_starts: dict[int, float] = {}
        self._ticker: asyncio.Task | None = None
        self._init_log(log_path)

    def on_dispatch_start(self):
        """Print legend and placeholder lines. Called after agent banner."""
        print(
            f"\n[dim]:high_voltage: Running {self.concurrency} tasks concurrently. Use --concurrency 1 for detailed output.[/dim]"
        )
        print("○ queued  ⊙ waiting  ● running  ◆ verifying  ✓ correct  ✗ incorrect  ⏭ skipped")
        print("")

    def on_init_started(self, i: int) -> None:
        self.states[i] = "⊙"
        self._render()

    def on_task_started(self, i: int, task: "Task", prompt: str) -> None:
        self._log_line(f"[{i + 1}/{self.total}] START task={task.id}")

    def on_agent_started(self, i: int) -> None:
        self.states[i] = "●"
        self._task_starts[i] = time.monotonic()
        self._render()

    def on_agent_finished(self, i: int, result: "AgentResult") -> None:
        if result.is_skipped:
            self._log_line(f"[{i + 1}/{self.total}] AGENT_SKIP reason={result.skip_reason}")
        else:
            self._log_line(f"[{i + 1}/{self.total}] AGENT_OK len={len(result.answer or '')}")

    def on_verify_started(self, i: int) -> None:
        self.states[i] = "◆"
        self._render()

    def on_verify_finished(self, i: int, vr: TaskVerificationResult) -> None:
        if vr.is_skipped:
            self._log_line(f"[{i + 1}/{self.total}] VERIFY skipped={vr.skip_reason}")
        else:
            self._log_line(f"[{i + 1}/{self.total}] VERIFY correct={vr.is_correct}")

    def on_task_finished(self, i: int, result: "TaskResult") -> None:
        elapsed = time.monotonic() - self._task_starts.pop(i, self._start)
        self._task_times.append(elapsed)
        self.completed += 1
        vr = result.verification
        if vr.is_skipped:
            self.states[i] = "⏭"
        elif vr.is_correct:
            self.states[i] = "✓"
            self.correct += 1
        else:
            self.states[i] = "✗"
            self.failed += 1
        if vr.is_skipped:
            reason = vr.skip_reason or "unknown"
            self._log_line(f"[{i + 1}/{self.total}] SKIP task={result.task_id} reason={reason} elapsed={elapsed:.1f}s")
        else:
            self._log_line(f"[{i + 1}/{self.total}] DONE task={result.task_id} elapsed={elapsed:.1f}s")
        self._render()

    def on_all_finished(self) -> None:
        if self._ticker:
            self._ticker.cancel()
        print()
        self._close_log()

    def start_ticker(self) -> asyncio.Task:
        self._ticker = asyncio.create_task(self._run_ticker())
        return self._ticker

    async def _run_ticker(self):
        while True:
            await asyncio.sleep(5)
            self._render()

    def _render(self):
        try:
            cols = os.get_terminal_size().columns
        except OSError:
            cols = 80

        skipped = self.completed - self.correct - self.failed
        suffix = f" {self.completed}/{self.total} ✓{self.correct} ✗{self.failed} ⏭{skipped}"
        if self.total + len(suffix) <= cols:
            bar = "".join(self.states)
            line1 = f"{bar}{suffix}"
        else:
            c = Counter(self.states)
            line1 = (
                f"○{c['○']} ⊙{c['⊙']} ●{c['●']} ◆{c['◆']} ✓{c['✓']} ✗{c['✗']} ⏭{c['⏭']} | {self.completed}/{self.total}"
            )

        elapsed = time.monotonic() - self._start
        if self._task_times:
            avg = sum(self._task_times) / len(self._task_times)
            remaining = self.total - self.completed
            eta = _format_duration(avg * remaining / max(self.concurrency, 1))
            line2 = f"⏱ avg {_format_duration(avg)}/task | elapsed {_format_duration(elapsed)} | ETA ~{eta}"
        else:
            line2 = f"⏱ elapsed {_format_duration(elapsed)}"

        print(f"\033[A\r\033[K{line1}\n\033[K{line2}", end="")


class PlainRenderer(_LogMixin):
    """Simple line output for non-tty environments (piped, file logging)."""

    verbose = False

    def __init__(self, total: int, log_path: Path | None = None):
        self.total = total
        self._init_log(log_path)

    def on_dispatch_start(self) -> None:
        pass

    def on_init_started(self, i: int) -> None:
        pass

    def start_ticker(self) -> "asyncio.Task | None":
        return None

    def on_task_started(self, i: int, task: "Task", prompt: str) -> None:
        self._log_line(f"[{i + 1}/{self.total}] START task={task.id}")

    def on_agent_started(self, i: int) -> None:
        pass

    def on_agent_finished(self, i: int, result: "AgentResult") -> None:
        if result.is_skipped:
            self._log_line(f"[{i + 1}/{self.total}] AGENT_SKIP reason={result.skip_reason}")

    def on_verify_started(self, i: int) -> None:
        pass

    def on_verify_finished(self, i: int, vr: TaskVerificationResult) -> None:
        pass

    def on_task_finished(self, i: int, result: "TaskResult") -> None:
        vr = result.verification
        if vr.is_skipped:
            status = "⏭"
        elif vr.is_correct:
            status = "✓"
        else:
            status = "✗"
        elapsed = result.report_entry.get("elapsed_time", 0)
        print(f"[{i + 1}/{self.total}] {result.task_id}: {status} ({elapsed:.1f}s)", builtin=True)
        if vr.is_skipped:
            reason = vr.skip_reason or "unknown"
            self._log_line(f"[{i + 1}/{self.total}] SKIP task={result.task_id} reason={reason} elapsed={elapsed:.1f}s")
        else:
            self._log_line(
                f"[{i + 1}/{self.total}] DONE task={result.task_id} elapsed={elapsed:.1f}s correct={vr.is_correct}"
            )

    def on_all_finished(self) -> None:
        self._close_log()


def select_renderer(
    total: int, concurrency: int, log_path: Path | None = None
) -> "VerboseRenderer | CompactRenderer | PlainRenderer":
    """Select appropriate renderer based on concurrency and terminal."""
    if not sys.stdout.isatty():
        return PlainRenderer(total, log_path=log_path)
    elif concurrency == 1:
        return VerboseRenderer(total, log_path=log_path)
    else:
        return CompactRenderer(total, concurrency, log_path=log_path)


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.0f}m {seconds % 60:.0f}s"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"
