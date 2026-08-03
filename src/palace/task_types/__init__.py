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

"""Task types package - exports all task types and base classes."""

from palace.task_types.agentic import AgenticTask
from palace.task_types.base import Task, TaskVerificationResult
from palace.task_types.classification import ClassificationTask
from palace.task_types.criteria_evaluation import CriteriaEvaluationTask, DEFAULT_CRITERIA
from palace.task_types.instruction_following import InstructionFollowingTask
from palace.task_types.qa import QATask

# Deprecated aliases (backward compatibility)
TaskType = Task
ClassificationTaskType = ClassificationTask
QATaskType = QATask

__all__ = [
    "Task",
    "TaskVerificationResult",
    "AgenticTask",
    "QATask",
    "ClassificationTask",
    "CriteriaEvaluationTask",
    "InstructionFollowingTask",
    "DEFAULT_CRITERIA",
    # Deprecated aliases
    "TaskType",
    "ClassificationTaskType",
    "QATaskType",
]
