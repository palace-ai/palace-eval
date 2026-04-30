"""Agentic task type — verifies via vivarium's /verify endpoint."""

from typing import Any

import requests

from palace.task_types.base import Task, TaskVerificationResult


class AgenticTask(Task):
    """Task type for agentic benchmarks evaluated via palace-vivarium."""

    _vivarium_url: str | None = None
    _env_id: str | None = None

    @property
    def initial_state(self) -> dict | None:
        return self.custom_fields.get("initial_state")

    @property
    def expected_outcome(self) -> dict:
        return self.custom_fields.get("expected_outcome", {})

    def adapt_prompt(self) -> str:
        return self.objective

    def verify(self, answer: str) -> TaskVerificationResult:
        if not self._vivarium_url or not self._env_id:
            return TaskVerificationResult(
                is_correct=False, is_skipped=True, skip_reason="vivarium_not_configured"
            )
        r = requests.post(
            f"{self._vivarium_url}/environments/{self._env_id}/verify",
            json={"expected_outcome": self.expected_outcome, "agent_answer": answer},
        )
        if r.status_code != 200:
            return TaskVerificationResult(
                is_correct=False, reasoning=f"Verify failed: {r.text}"
            )
        data = r.json()
        return TaskVerificationResult(
            is_correct=data["is_correct"],
            reasoning=data.get("reasoning"),
            metrics=data.get("metrics", {}),
        )

    @classmethod
    def aggregate(cls, results: list[TaskVerificationResult]) -> dict[str, Any]:
        evaluated = [r for r in results if not r.is_skipped]
        if not evaluated:
            return {"accuracy": 0}
        correct = sum(1 for r in evaluated if r.is_correct)
        accuracy = correct / len(evaluated)
        # Average agent metrics from results
        metric_keys = ["steps", "tool_calls", "wall_time_seconds"]
        avg_agent: dict[str, float] = {}
        for key in metric_keys:
            values = [r.metrics.get(key) for r in evaluated if key in r.metrics]
            if values:
                avg_agent[f"avg_{key}"] = sum(values) / len(values)
        return {"accuracy": accuracy, **avg_agent}
