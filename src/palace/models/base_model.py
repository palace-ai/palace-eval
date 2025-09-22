from abc import ABC, abstractmethod
from typing import Dict, List


class Model(ABC):
    """Base class for all language models."""

    @property
    @abstractmethod
    def name(self):
        """The name of the model."""
        pass

    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Generate a response given a conversation history.

        Args:
            messages: List of message dictionaries, each with `role` and `content` keys. `role` can be either `system`, `user`, `assistant`, or `tool`. Optionally, there may be an additional `tool_name` key.
            **kwargs: Additional model-specific parameters

        Returns:
            The model's response as a string
        """
        pass
