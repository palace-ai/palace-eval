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
    def run(self, prompt: str, image: str | None = None) -> tuple[str, dict[str, Any] | None]:
        """Run the agent on the given prompt and return an answer.

        Args:
            prompt: The text prompt for the agent
            image: Optional path to an image file for multimodal tasks
        """
        pass
