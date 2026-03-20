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

    def expected_display(self, task: "Task") -> str | None:
        """Return a human-readable expected answer for display/logging purposes.
        
        Subclasses should override this to provide task-type-specific formatting.
        Default implementation returns task.expected.
        """
        return task.expected


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
        from palace.task_types.classification import ClassificationTaskType
        from palace.task_types.qa import QATaskType
        from palace.task_types.report_generation import ReportGenerationTaskType
        from palace.utils.printing import print

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
            "QA": QATaskType,
            "Report Generation": ReportGenerationTaskType,
            "Classification": ClassificationTaskType,
        }

        if task_type_name not in task_type_map:
            raise ValueError(f"Unknown task_type '{task_type_name}'. Valid types: {list(task_type_map.keys())}")

        task = cls.__new__(cls)
        task.id = data["id"]
        task.objective = data["objective"]
        task.task_type = task_type_map[task_type_name]()
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
