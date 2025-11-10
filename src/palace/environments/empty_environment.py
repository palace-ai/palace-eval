from palace.environments.base_environment import Environment
from palace.tools import Tool


class EmptyEnvironment(Environment):
    @property
    def name(self) -> str:
        return "Empty Environment"

    @property
    def description(self) -> str:
        return """This environment is empty. The agent will not use any tools."""

    @property
    def tools(self) -> list[Tool]:
        return []

    @property
    def environment_prompt(self) -> str:
        return ""
