"""Agentic task type — verifies via vivarium's /exec endpoint."""

from typing import Any

from palace.task_types.base import Task, TaskVerificationResult


class AgenticTask(Task):
    """Task type for agentic benchmarks evaluated via vivarium."""

    _vivarium_url: str | None = None
    _env_id: str | None = None
    _verify_fn = None
    _verify_context_decl: dict = {}

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

    def verify(self, answer: str) -> TaskVerificationResult:
        if not self._vivarium_url or not self._env_id:
            return TaskVerificationResult(
                is_correct=False, is_skipped=True, skip_reason="vivarium_not_configured"
            )
        if not self._verify_fn:
            return TaskVerificationResult(
                is_correct=False, is_skipped=True, skip_reason="no_verify_function"
            )

        from vivarium import Container
        container = Container(self._vivarium_url, self._env_id)

        # Copy verify_files if present in tasklist
        self._inject_verify_files(container)

        try:
            result = self._verify_fn(self.expected_outcome, answer, container)
        except Exception as e:
            return TaskVerificationResult(
                is_correct=False, reasoning=f"Verify failed: {e}"
            )

        return _normalize_verify_result(result)

    def _inject_verify_files(self, container) -> None:
        """Copy tamper-proof verify_files into the container if they exist."""
        if not hasattr(self, '_tasklist_path') or not self._tasklist_path:
            return
        verify_files_dir = self._tasklist_path / "environment" / "verify_files"
        if not verify_files_dir.is_dir():
            return
        # Find task-specific verify files
        task_dir = verify_files_dir / self.id
        if not task_dir.is_dir():
            return
        import shlex
        for f in task_dir.rglob("*"):
            if f.is_file():
                dest = f"/verify_files/{f.relative_to(task_dir)}"
                container.exec(f"mkdir -p $(dirname {shlex.quote(dest)})")
                container.write(dest, f.read_bytes())

    @classmethod
    def aggregate(cls, results: list[TaskVerificationResult]) -> dict[str, Any]:
        evaluated = [r for r in results if not r.is_skipped]
        if not evaluated:
            return {"accuracy": 0}
        correct = sum(1 for r in evaluated if r.is_correct)
        accuracy = correct / len(evaluated)
        metric_keys = ["steps", "tool_calls", "wall_time_seconds"]
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
        return TaskVerificationResult(
            is_correct=float(result) >= 1.0, metrics={"score": float(result)}
        )
    if isinstance(result, dict):
        return TaskVerificationResult(
            is_correct=result.get("is_correct", False),
            reasoning=result.get("reasoning"),
            metrics=result.get("metrics", {}),
        )
    return TaskVerificationResult(is_correct=False, reasoning=f"Unexpected verify result: {result}")
