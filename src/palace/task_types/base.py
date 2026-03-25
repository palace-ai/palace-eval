"""Base classes for tasks and task verification."""

from dataclasses import dataclass, field
from typing import Any, Self


@dataclass
class TaskVerificationResult:
    """Structured result from task verification with optional metrics."""

    is_correct: bool
    reasoning: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


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
    document: str | None
    attachment: str | None
    custom_verificator: str | None
    custom_fields: dict[str, Any]

    def adapt_prompt(self) -> str:
        """Build the task prompt. Subclasses must override."""
        raise NotImplementedError("Subclasses must implement adapt_prompt().")

    def verify(self, answer: str) -> tuple[bool, str | None] | TaskVerificationResult:
        """Verify the answer. Subclasses must override."""
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
    def aggregate(cls, results: list[TaskVerificationResult]) -> dict[str, Any]:
        """Compute aggregate metrics from all task results.
        Default: accuracy only. Subclasses override for richer metrics.
        """
        if not results:
            return {"accuracy": 0}
        correct = sum(1 for r in results if r.is_correct)
        return {"accuracy": correct / len(results)}

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Create a Task instance from a dictionary."""
        # Import here to avoid circular imports
        from palace.task_types.classification import ClassificationTask
        from palace.task_types.qa import QATask
        from palace.task_types.report_generation import ReportGenerationTask
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
            "QA": QATask,
            "Classification": ClassificationTask,
            "Report Generation": ReportGenerationTask,
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
        task.document = data.get("document")
        task.attachment = data.get("attachment")
        task.custom_verificator = data.get("custom_verificator")
        task.custom_fields = {
            k: v for k, v in data.items() if k not in required_fields + optional_fields
        }
        return task

    def __init__(self):
        raise NotImplementedError("Use Task.from_dict() to create Task instances.")
