"""Task types package - exports all task types and base classes."""

from palace.task_types.base import Task, TaskType, TaskVerificationResult
from palace.task_types.report_generation import (
    DEFAULT_CRITERIA,
    ReportGenerationTaskType,
)
from palace.task_types.task_types import (
    MLCTaskType,
    QATaskType,
    SycophancyBinaryTaskType,
    SycophancyOpenEndedTaskType,
)

__all__ = [
    "Task",
    "TaskType",
    "TaskVerificationResult",
    "QATaskType",
    "MLCTaskType",
    "SycophancyBinaryTaskType",
    "SycophancyOpenEndedTaskType",
    "ReportGenerationTaskType",
    "DEFAULT_CRITERIA",
]
