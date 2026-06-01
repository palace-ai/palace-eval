"""Task types package - exports all task types and base classes."""

from palace.task_types.agentic import AgenticTask
from palace.task_types.base import Task, TaskVerificationResult
from palace.task_types.classification import ClassificationTask
from palace.task_types.criteria_evaluation import CriteriaEvaluationTask, DEFAULT_CRITERIA
from palace.task_types.instruction_following import InstructionFollowingTask
from palace.task_types.qa import QATask
from palace.task_types.report_generation import ReportGenerationTask

# Deprecated aliases (backward compatibility)
TaskType = Task
ClassificationTaskType = ClassificationTask
QATaskType = QATask
ReportGenerationTaskType = ReportGenerationTask

__all__ = [
    "Task",
    "TaskVerificationResult",
    "AgenticTask",
    "QATask",
    "ClassificationTask",
    "CriteriaEvaluationTask",
    "InstructionFollowingTask",
    "ReportGenerationTask",
    "DEFAULT_CRITERIA",
    # Deprecated aliases
    "TaskType",
    "ClassificationTaskType",
    "QATaskType",
    "ReportGenerationTaskType",
]
