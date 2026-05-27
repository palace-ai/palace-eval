"""Base class for analyzers that run after task verification."""

from abc import ABC, abstractmethod
from typing import Any

from palace.task_types import Task, TaskVerificationResult


class Analyzer(ABC):
    """Base class for post-verification analyzers.
    
    Analyzers inspect task outputs and produce additional metrics.
    Each analyzer declares which task types it supports.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return analyzer name used as metrics key."""
        pass

    @property
    def supported_task_types(self) -> list[type[Task]]:
        """Task classes this analyzer applies to. Empty = none (must override)."""
        return []

    @abstractmethod
    async def analyze(
        self,
        task: Task,
        answer: str,
        verification_result: TaskVerificationResult,
    ) -> dict[str, Any]:
        """Analyze task output and return metrics dict.
        
        Args:
            task: The task that was evaluated
            answer: The agent's answer
            verification_result: Result from task.verify()
            
        Returns:
            Dict of metrics to store under metrics.analyzers.<name>
        """
        pass

    def format_summary(self, metrics: dict[str, Any]) -> str:
        """Format metrics as human-readable summary for console output.
        
        Override in subclasses for custom formatting.
        Default: key-value pairs.
        """
        return "\n".join(f"{k}: {v}" for k, v in metrics.items())
