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

"""Base classes for tasks and task verification."""

from dataclasses import dataclass, field
from typing import Any, Protocol, Self


class ExecutionEnvironment(Protocol):
    """Interface for agentic task verification — exec/read/write on a container."""

    async def exec(self, cmd: str, timeout: int = 120) -> tuple[int, str]: ...
    async def read(self, path: str) -> str: ...
    async def write(self, path: str, content: bytes) -> None: ...


@dataclass
class TaskVerificationResult:
    """Structured result from task verification with optional metrics.

    Outcomes:
        - "correct": model answered correctly
        - "incorrect": model answered incorrectly
        - "error": infrastructure/transient failure (excluded from score)
        - "unsupported": model capability limitation (optionally penalized)
    """

    is_correct: bool
    outcome: str = ""  # auto-set in __post_init__ if empty
    reason: str | None = None
    reasoning: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.outcome:
            self.outcome = "correct" if self.is_correct else "incorrect"

    @property
    def is_skipped(self) -> bool:
        """Backward compat: True when outcome is error or unsupported."""
        return self.outcome in ("error", "unsupported")

    @property
    def skip_reason(self) -> str | None:
        """Backward compat: returns reason for error/unsupported outcomes."""
        return self.reason if self.is_skipped else None


class Task:
    """
    Base class for all tasks. Subclasses implement task-type-specific behavior.

    Instances must be created using the `from_dict()` factory method.
    """

    id: str
    objective: str
    expected: str | None
    references: str | None
    difficulty: str | None
    group: str | None
    document: str | None
    attachments: list[str]
    custom_verificator: str | None
    custom_fields: dict[str, Any]

    @property
    def attachment(self) -> str | None:
        """Backward compat: first attachment or None."""
        return self.attachments[0] if self.attachments else None

    def adapt_prompt(self) -> str:
        """Build the task prompt. Subclasses must override."""
        raise NotImplementedError("Subclasses must implement adapt_prompt().")

    async def verify(
        self, answer: str, env: ExecutionEnvironment | None = None
    ) -> tuple[bool, str | None] | TaskVerificationResult:
        """Verify the answer. Subclasses must override.

        Args:
            answer: The agent's response to evaluate.
            env: Optional execution environment for agentic verification.
        """
        raise NotImplementedError("Subclasses must implement verify().")

    def expected_display(self) -> str | None:
        """Return a human-readable expected answer for display/logging.
        Subclasses may override for task-type-specific formatting.
        """
        return self.expected

    def create_prompt(self) -> str:
        """Adapt the task prompt based on its task type."""
        return self.adapt_prompt()

    @classmethod
    def aggregate(cls, results: list[TaskVerificationResult], penalize_unsupported: bool = False) -> dict[str, Any]:
        """Compute aggregate metrics from all task results.

        Default implementation computes accuracy only.
        Subclasses override for richer metrics (e.g., F1, normalized scores).

        When penalize_unsupported is False (default), only correct/incorrect
        outcomes are included in the denominator (backward-compatible behavior).
        When True, unsupported outcomes also count in the denominator (scored as 0).
        Error outcomes are always excluded.

        Args:
            results: List of verification results from all evaluated tasks.
            penalize_unsupported: If True, unsupported tasks count as failures
                in the score. If False, they are excluded like errors.

        Returns:
            Dict of metric names to values. Always includes "accuracy".
        """
        if penalize_unsupported:
            # Denominator = correct + incorrect + unsupported (exclude only errors)
            evaluated = [r for r in results if r.outcome != "error"]
        else:
            # Denominator = correct + incorrect only (legacy behavior)
            evaluated = [r for r in results if not r.is_skipped]
        if not evaluated:
            return {"accuracy": 0}
        correct = sum(1 for r in evaluated if r.is_correct)
        return {"accuracy": correct / len(evaluated)}

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Create a Task instance from a dictionary.

        Dispatches to the appropriate subclass based on the ``task_type`` field.

        Args:
            data: Task dictionary with required keys ``id``, ``objective``,
                and ``task_type``, plus optional fields like ``expected``,
                ``references``, ``difficulty``, ``document``, ``attachment``.

        Returns:
            A Task subclass instance matching the specified task type.

        Raises:
            ValueError: If required fields are missing or task_type is unknown.
        """
        # Import here to avoid circular imports
        from palace.task_types.agentic import AgenticTask
        from palace.task_types.classification import ClassificationTask
        from palace.task_types.criteria_evaluation import CriteriaEvaluationTask
        from palace.task_types.instruction_following import InstructionFollowingTask
        from palace.task_types.qa import QATask
        from palace.utils.printing import print

        required_fields = ["id", "objective", "task_type"]
        optional_fields = [
            "expected",
            "references",
            "difficulty",
            "group",
            "document",
            "attachment",
            "attachments",
            "custom_verificator",
        ]

        for f in required_fields:
            if f not in data:
                raise ValueError(f"Missing required field '{f}' in task data.")

        task_type_name = data["task_type"]

        # Deprecated aliases with warnings
        deprecated_aliases = {
            "Sycophancy-Binary": ("Classification", "Use task_type='Classification' with labels config"),
            "Sycophancy-OpenEnded": ("QA", "Use task_type='QA' with correctness_criterion and references config"),
            "MLC": ("Classification", "Use task_type='Classification'"),
            "Long Context QA": ("QA", "Use task_type='QA'"),
            "Claim Verification": ("QA", "Use task_type='QA'"),
        }
        if task_type_name in deprecated_aliases:
            new_name, guidance = deprecated_aliases[task_type_name]
            print(f"[yellow][DEPRECATED] task_type '{task_type_name}' is deprecated. {guidance}[/yellow]")
            task_type_name = new_name

        task_type_map = {
            "QA": QATask,
            "Classification": ClassificationTask,
            "Criteria Evaluation": CriteriaEvaluationTask,
            "Instruction Following": InstructionFollowingTask,
            "Agentic": AgenticTask,
        }

        if task_type_name not in task_type_map:
            raise ValueError(f"Unknown task_type '{task_type_name}'. Valid types: {list(task_type_map.keys())}")

        subclass = task_type_map[task_type_name]
        task = subclass.__new__(subclass)
        task.id = data["id"]
        task.objective = data["objective"]
        task.expected = data.get("expected")
        task.references = data.get("references")
        task.difficulty = data.get("difficulty")
        task.group = data.get("group")
        task.document = data.get("document")
        task.attachments = data.get("attachments") or (
            [data["attachment"]] if data.get("attachment") else []
        )  # "attachment" is deprecated shorthand for "attachments": [x]
        task.custom_verificator = data.get("custom_verificator")
        task.custom_fields = {k: v for k, v in data.items() if k not in required_fields + optional_fields}

        return task

    def __init__(self):
        raise NotImplementedError("Use Task.from_dict() to create Task instances.")
