from typing import Any

from mcp.types import CallToolResult, TextContent

from palace.agents import Agent
from palace.environments.base_environment import Environment
from palace.environments.unknown_environment import UnknownEnvironment
from palace.mcp_utils.mcp_client import MCPClientPool
from palace.models.openai_compatible_model import OpenAICompatibleModel


class OpenAIAPIAgent(Agent):
    """A class to connect to a remote agent deployed via OpenAI-compatible AI and call it as a black box.
    This class can also be used to test a normal LLM with no agentic behaviour, using the same agent evaluation pipeline.
    Metrics are not supported for this agent type yet.
    """

    def __init__(self, url: str, token: str | None = None, name: str | None = None):
        self.url = url
        self.token = token
        self._name = name
        self._environment = UnknownEnvironment()

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return "Unknown remote model"

    @property
    def paradigm_name(self) -> str:
        return "Unknown remote paradigm"

    @property
    def environment(self) -> Environment:
        return self._environment

    def run(self, task: str) -> tuple[str, dict[str, Any] | None]:
        agent = OpenAICompatibleModel(self.url, self.token, self.name)
        try:
            output = agent.generate([{"role": "user", "content": task}])
        except Exception as e:
            print(f"OpenAIAPI agent returned the following exception: \n{e}")
            raise e

        return output, {}
