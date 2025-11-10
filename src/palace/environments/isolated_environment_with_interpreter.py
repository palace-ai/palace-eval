from palace.environments.base_environment import Environment
from palace.tools import FinalAnswerTool, HumanTool, PythonInterpreterTool, Tool


class IsolatedEnvironmentWithInterpreter(Environment):
    def __init__(self):
        self._tools = [
            HumanTool(),
            PythonInterpreterTool(),
            FinalAnswerTool(),
        ]

    @property
    def name(self) -> str:
        """Return the name of the environment."""
        return "Isolated Environment With Interpreter"

    @property
    def description(self) -> str:
        """Return the description of the environment."""
        return """This environment is isolated from the outside world. There are no "external" tools that you can use to help the user. However, you can still ask the user for his feedback, so use this opportunity to work through the problem with him, he will appreciate discussing with you. Also, you can execute arbitrary Python code, but be careful with what you run and don't break anything."""

    @property
    def tools(self) -> list[Tool]:
        return self._tools
