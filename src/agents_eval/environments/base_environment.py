from abc import ABC, abstractmethod
from typing import List

from agents_eval.tools import Tool


class Environment(ABC):
    """Base Environment class."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the environment."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return the description of the environment."""
        pass

    @property
    @abstractmethod
    def tools(self) -> List[Tool]:
        """Return the list of tools available in the environment."""
        pass

    @property
    def environment_prompt(self) -> str:
        return f"""This is a detailed overview of the environment that you will be working in while solving the provided task:
Environment name: {self.name}
Environment description: {self.description}
Available tools in this environment that you can use: {
            "".join(
                [
                    f'''
    {i + 1}. {tool.name}
    {tool.description}
    Tool parameters:
        {tool.parameters}
    Required parameters:
        {tool.required_parameters}'''
                    for i, tool in enumerate(self.tools)
                ]
            )
        }
"""

    @property
    def _environment_prompt_without_tools(self) -> str:
        return f"""This is a detailed overview of the environment that you will be working in while solving the provided task:
Environment name: {self.name}
Environment description: {self.description}
"""
