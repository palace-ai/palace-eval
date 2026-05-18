from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from palace.task_types.base import Task


class Agent(ABC):
    """Base class that defines the agent interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def run(self, prompt: str, image: str | None = None) -> tuple[str | None, dict[str, Any] | None]:
        """Run the agent on the given prompt and return an answer.

        Args:
            prompt: The text prompt for the agent
            image: Optional path to an image file for multimodal tasks

        Returns:
            Tuple of (answer, metrics). answer is None if the agent failed to respond.
        """
        pass

    def on_tasklist_start(self, tasklist_path: Path, info: dict) -> None:
        """Called before evaluating a tasklist. Override for setup."""
        pass

    def on_tasklist_end(self) -> None:
        """Called after evaluating a tasklist. Override for cleanup."""
        pass

    def on_task_start(self, task: "Task") -> None:
        """Called before each task. Override for per-task setup."""
        pass

    def on_task_end(self, task: "Task") -> None:
        """Called after each task (including verify). Override for per-task cleanup."""
        pass
