from typing import List

from agents_eval.environments import Environment
from agents_eval.tools import FinalAnswerTool, HumanTool, LetterCountTool, Tool


class IsolatedEnvironmentWithLetterCount(Environment):
    def __init__(self):
        self._tools = [
            HumanTool(),
            FinalAnswerTool(),
            LetterCountTool(),
        ]

    @property
    def name(self) -> str:
        """Return the name of the environment."""
        return "Isolated Environment With Letter Count"

    @property
    def description(self) -> str:
        """Return the description of the environment."""
        return """This environment is mostly isolated from the outside world. 
There are very few tools that you can use to help the user.
Basically, the only "external" tool is the Letter Count Tool, which can be used to find the number of occurrences of a letter within a word.
Besides that, you can ask the user for his feedback, and he will very much appreciate discussing with you.
"""

    @property
    def tools(self) -> List[Tool]:
        return self._tools
