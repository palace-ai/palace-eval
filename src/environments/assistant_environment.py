from typing import List

import tools

from . import Environment


class AssistantEnvironment(Environment):
    def __init__(self):
        self._tools = [
            tools.AIAssistantTool(),
            tools.FinalAnswerTool(),
        ]

    @property
    def name(self) -> str:
        """Return the name of the environment."""
        return "Assistant Environment"

    @property
    def description(self) -> str:
        """Return the description of the environment."""
        return """This environment is isolated from the outside world.
There are no "external" tools that you can use to help the user.
However, you can ask an AI assistant to help you, so use this opportunity.
You can ask him all kinds of questions, he will be happy to help."""

    @property
    def tools(self) -> List[tools.Tool]:
        return self._tools
