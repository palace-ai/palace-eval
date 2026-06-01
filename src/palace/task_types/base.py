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
    """Structured result from task verification with optional metrics."""

    is_correct: bool
    reasoning: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    is_skipped: bool = False
    skip_reason: str | None = None


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

    async def verify(self, answer: str, env: ExecutionEnvironment | None = None) -> tuple[bool, str | None] | TaskVerificationResult:
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
    def aggregate(cls, results: list[TaskVerificationResult]) -> dict[str, Any]:
        """Compute aggregate metrics from all task results.

        Default implementation computes accuracy only.
        Subclasses override for richer metrics (e.g., F1, normalized scores).
        Skipped tasks are excluded from all calculations.

        Args:
            results: List of verification results from all evaluated tasks.

        Returns:
            Dict of metric names to values. Always includes "accuracy".
        """
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
        from palace.task_types.report_generation import ReportGenerationTask
        from palace.utils.printing import print

        required_fields = ["id", "objective", "task_type"]
        optional_fields = [
            "expected",
            "references",
            "difficulty",
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
            "Report Generation": ReportGenerationTask,
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
        task.document = data.get("document")
        task.attachments = data.get("attachments") or ([data["attachment"]] if data.get("attachment") else [])
        task.custom_verificator = data.get("custom_verificator")
        task.custom_fields = {
            k: v for k, v in data.items() if k not in required_fields + optional_fields
        }

        return task

    def __init__(self):
        raise NotImplementedError("Use Task.from_dict() to create Task instances.")
