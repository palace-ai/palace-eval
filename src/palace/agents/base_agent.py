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

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from palace.evaluation.types import AgentResult, Attachment
    from palace.task_types.base import ExecutionEnvironment, Task


class Agent(ABC):
    """Base class that defines the agent interface."""

    verbose: bool = True
    agentic: bool = False

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def run(self, prompt: str, attachments: "list[Attachment] | None" = None, *, task_id: str | None = None) -> "AgentResult":
        """Run the agent on the given prompt and return a result.

        Args:
            prompt: The text prompt for the agent
            attachments: Optional list of Attachment objects for multimodal tasks
            task_id: Optional task identifier for agents that need to correlate
                with per-task state (e.g. VivariumAgent environments)

        Returns:
            AgentResult with answer, metrics, and skip status.
        """
        pass

    async def on_tasklist_start(self, tasklist_path: Path, info: dict) -> None:
        """Called before evaluating a tasklist. Override for setup."""
        pass

    async def on_tasklist_end(self) -> None:
        """Called after evaluating a tasklist. Override for cleanup."""
        pass

    async def on_task_start(self, task: "Task") -> "ExecutionEnvironment | None":
        """Called before each task. Return execution environment for agentic verification."""
        return None

    async def on_task_end(self, task: "Task") -> None:
        """Called after each task (including verify). Override for per-task cleanup."""
        pass
