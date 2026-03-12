"""Base classes for task types and task verification."""

from dataclasses import dataclass, field
from typing import Any, Self


@dataclass
class TaskVerificationResult:
    """Structured result from task verification with optional metrics."""

    is_correct: bool
    reasoning: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


class TaskType:
    """Base class for task types."""

    def adapt_prompt(self, task: "Task") -> str:
        """Adapt the prompt of the given task according to the specific task type logic."""
        raise NotImplementedError("Subclasses must implement the adapt_prompt method.")

    def verify(
        self, task: "Task", answer: str
    ) -> tuple[bool, str | None] | TaskVerificationResult:
        """Verify the task using task type-specific logic."""
        raise NotImplementedError("Subclasses must implement the verify method.")


class Task:
    """
    Represents a task.

    Instances must be created using the `from_dict()` factory method.
    """

    id: str
    objective: str
    task_type: TaskType
    expected: str | None
    references: str | None
    difficulty: str | None
    document: str | None
    attachment: str | None
    custom_verificator: str | None
    custom_fields: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Create a Task instance from a dictionary."""
        # Import here to avoid circular imports
        from palace.task_types.task_types import (
            MLCTaskType,
            QATaskType,
            SycophancyBinaryTaskType,
            SycophancyOpenEndedTaskType,
        )
        from palace.task_types.report_generation import ReportGenerationTaskType

        required_fields = ["id", "objective", "task_type"]
        optional_fields = [
            "expected",
            "references",
            "difficulty",
            "document",
            "attachment",
            "custom_verificator",
        ]

        for f in required_fields:
            if f not in data:
                raise ValueError(f"Missing required field '{f}' in task data.")

        task = cls.__new__(cls)
        task.id = data["id"]
        task.objective = data["objective"]
        task.task_type = {
            "QA": QATaskType,
            "Long Context QA": QATaskType,
            "Claim Verification": QATaskType,
            "Report Generation": ReportGenerationTaskType,
            "Sycophancy-Binary": SycophancyBinaryTaskType,
            "Sycophancy-OpenEnded": SycophancyOpenEndedTaskType,
            "MLC": MLCTaskType,
        }[data["task_type"]]()
        task.expected = data.get("expected")
        task.references = data.get("references")
        task.difficulty = data.get("difficulty")
        task.document = data.get("document")
        task.attachment = data.get("attachment")
        task.custom_verificator = data.get("custom_verificator")
        task.custom_fields = {
            k: v for k, v in data.items() if k not in required_fields + optional_fields
        }
        return task

    def __init__(self):
        raise NotImplementedError("Use Task.from_dict() to create Task instances.")

    def create_prompt(self) -> str:
        """Adapt the task prompt based on its task type."""
        return self.task_type.adapt_prompt(self)

    def verify(self, result: str) -> tuple[bool, str | None] | TaskVerificationResult:
        """Verify the task using task type-specific logic."""
        return self.task_type.verify(self, result)
