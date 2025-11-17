from abc import ABC, abstractmethod
from typing import Any

from palace.environments.base_environment import Environment


class Agent(ABC):
    """Base class that defines the agent interface.
    This class is used to define general agent classes (local agent, mcp agent, api agent), not specific agentic paradigms.
    """

    @property
    @abstractmethod
    def name(str) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @property
    @abstractmethod
    def paradigm_name(self) -> str:
        pass

    @property
    @abstractmethod
    def environment(self) -> Environment:
        pass

    @abstractmethod
    def run(self, task: str) -> tuple[str, dict[str, Any] | None]:
        """Run the agent on the given task and return an answer."""
        pass
