"""Task types package - exports all task types and base classes."""

from palace.task_types.base import Task, TaskVerificationResult
from palace.task_types.classification import ClassificationTask
from palace.task_types.qa import QATask
from palace.task_types.report_generation import (
    DEFAULT_CRITERIA,
    ReportGenerationTask,
)

# Deprecated aliases (backward compatibility)
TaskType = Task
ClassificationTaskType = ClassificationTask
QATaskType = QATask
ReportGenerationTaskType = ReportGenerationTask

__all__ = [
    "Task",
    "TaskVerificationResult",
    "QATask",
    "ClassificationTask",
    "ReportGenerationTask",
    "DEFAULT_CRITERIA",
    # Deprecated aliases
    "TaskType",
    "ClassificationTaskType",
    "QATaskType",
    "ReportGenerationTaskType",
]
