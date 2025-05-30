from typing import List

from agents_eval.environments.base_environment import Environment
from agents_eval.tools import FinalAnswerTool, HumanTool, Tool


class IsolatedEnvironment(Environment):
    def __init__(self):
        self._tools = [
            HumanTool(),
            FinalAnswerTool(),
        ]

    @property
    def name(self) -> str:
        """Return the name of the environment."""
        return "Isolated Environment"

    @property
    def description(self) -> str:
        """Return the description of the environment."""
        return """This environment is isolated from the outside world. There are no "external" tools that you can use to help the user. However, you can still ask the user for his feedback, so use this opportunity to work through the problem with him, he will appreciate discussing with you.
"""

    @property
    def tools(self) -> List[Tool]:
        return self._tools
