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

"""Agentic task type — verifies via execution environment."""

import inspect
import shlex
from pathlib import Path
from typing import Any, Callable

from palace.task_types.base import ExecutionEnvironment, Task, TaskVerificationResult


class AgenticTask(Task):
    """Task type for agentic benchmarks evaluated via vivarium.

    Attributes set by orchestrator during task loading:
        _verify_fn: The verify function loaded from environment/verify.py
        _tasklist_path: Path to the tasklist directory
    """

    _verify_fn: Callable | None = None
    _tasklist_path: Path | None = None

    @property
    def seed_args(self) -> dict | None:
        return self.custom_fields.get("seed_args")

    @property
    def expected_outcome(self) -> dict:
        return self.custom_fields.get("expected_outcome", {})

    def adapt_prompt(self) -> str:
        return self.objective

    def expected_display(self) -> str | None:
        return None

    async def verify(self, answer: str, env: ExecutionEnvironment | None = None) -> TaskVerificationResult:
        if env is None:
            return TaskVerificationResult(is_correct=False, outcome="error", reason="no_execution_environment")
        if not self._verify_fn:
            return TaskVerificationResult(is_correct=False, outcome="error", reason="no_verify_function")

        # Copy verify_files if present in tasklist
        await self._inject_verify_files(env)

        try:
            result = self._verify_fn(self.expected_outcome, answer, env)
            if inspect.isawaitable(result):
                result = await result
        except Exception as e:
            return TaskVerificationResult(is_correct=False, reasoning=f"Verify failed: {e}")

        return _normalize_verify_result(result)

    async def _inject_verify_files(self, env: ExecutionEnvironment) -> None:
        """Copy tamper-proof verify_files into the container if they exist."""
        if not self._tasklist_path:
            return
        verify_files_dir = self._tasklist_path / "environment" / "verify_files"
        if not verify_files_dir.is_dir():
            return
        task_dir = verify_files_dir / self.id
        if not task_dir.is_dir():
            return
        for f in task_dir.rglob("*"):
            if f.is_file():
                dest = f"/verify_files/{f.relative_to(task_dir)}"
                await env.exec(f"mkdir -p $(dirname {shlex.quote(dest)})")
                await env.write(dest, f.read_bytes())

    @classmethod
    def aggregate(cls, results: list[TaskVerificationResult], penalize_unsupported: bool = False) -> dict[str, Any]:
        evaluated = [r for r in results if not r.is_skipped]
        if not evaluated:
            return {"accuracy": 0}
        correct = sum(1 for r in evaluated if r.is_correct)
        accuracy = correct / len(evaluated)
        metric_keys = ["steps", "tool_calls", "duration_seconds"]
        avg_agent: dict[str, float] = {}
        for key in metric_keys:
            values = [r.metrics[key] for r in evaluated if key in r.metrics and r.metrics[key] is not None]
            if values:
                avg_agent[f"avg_{key}"] = sum(values) / len(values)
        return {"accuracy": accuracy, **avg_agent}


def _normalize_verify_result(result) -> TaskVerificationResult:
    """Normalize verify return value: bool, float, or dict → TaskVerificationResult."""
    if isinstance(result, bool):
        return TaskVerificationResult(is_correct=result, reasoning="")
    if isinstance(result, (int, float)):
        return TaskVerificationResult(is_correct=float(result) >= 1.0, metrics={"score": float(result)})
    if isinstance(result, dict):
        return TaskVerificationResult(
            is_correct=result.get("is_correct", False),
            reasoning=result.get("reasoning"),
            metrics=result.get("metrics", {}),
        )
    return TaskVerificationResult(is_correct=False, reasoning=f"Unexpected verify result: {result}")
