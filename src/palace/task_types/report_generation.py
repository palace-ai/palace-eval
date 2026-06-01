"""Backward compatibility — ReportGenerationTask is now CriteriaEvaluationTask."""

from palace.task_types.criteria_evaluation import CriteriaEvaluationTask, DEFAULT_CRITERIA

# Alias for backward compatibility
ReportGenerationTask = CriteriaEvaluationTask

__all__ = ["ReportGenerationTask", "CriteriaEvaluationTask", "DEFAULT_CRITERIA"]
