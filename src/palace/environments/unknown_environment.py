from palace.environments.base_environment import Environment
from palace.tools import Tool


class UnknownEnvironment(Environment):
    def __init__(self):
        self._tools = []

    @property
    def name(self) -> str:
        return "Unknown Remote Environment"

    @property
    def description(self) -> str:
        return """This environment is unknown because the agent is using it behind the server as a black box."""

    @property
    def tools(self) -> list[Tool]:
        return self._tools
