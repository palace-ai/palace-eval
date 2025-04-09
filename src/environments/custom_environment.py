from typing import List

from tools import FinalAnswerTool, Tool

from . import Environment


class CustomEnvironment(Environment):
    def __init__(self, tools: List[Tool]):
        self._tools = tools

        # Add FinalAnswerTool if it is not provided explicitly
        if "Final Answer Tool" not in [tool.name for tool in tools]:
            self._tools.append(FinalAnswerTool())

    @property
    def name(self) -> str:
        """Return the name of the environment."""
        return "Custom Environment"

    @property
    def description(self) -> str:
        """Return the description of the environment."""
        return """This environment is custom made, and contains only the tools that have been explicitly provided during initialization."""

    @property
    def tools(self) -> List[Tool]:
        return self._tools
