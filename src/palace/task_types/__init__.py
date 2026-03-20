"""Task types package - exports all task types and base classes."""

from palace.task_types.base import Task, TaskType, TaskVerificationResult
from palace.task_types.classification import ClassificationTaskType
from palace.task_types.qa import QATaskType
from palace.task_types.report_generation import (
    DEFAULT_CRITERIA,
    ReportGenerationTaskType,
)

__all__ = [
    "Task",
    "TaskType",
    "TaskVerificationResult",
    "QATaskType",
    "ClassificationTaskType",
    "ReportGenerationTaskType",
    "DEFAULT_CRITERIA",
]
