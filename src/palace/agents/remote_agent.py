from typing import Optional

from palace.agents import Agent
from palace.environments.base_environment import Environment
from palace.environments.unknown_environment import UnknownEnvironment
from palace.mcp_utils.mcp_client import MCPClientPool


class RemoteAgent(Agent):
    """A class to connect to a remote agent deployed via MCP and call it as a black box."""

    def __init__(
        self, url: str, token: Optional[str] = None, name: Optional[str] = None
    ):
        self.url = url
        self.token = token
        self._environment = UnknownEnvironment()

        with MCPClientPool.get_connection(url, token) as mcp_client:
            available_agents = [tool.name for tool in mcp_client.list_tools().tools]

        if len(available_agents) == 0:
            raise ValueError(f"There is no agent or tool at {url}.")

        if name is not None and name in available_agents:
            self._name = name
        elif name is not None and name not in available_agents:
            raise ValueError(
                f"There is no agent with the provided name {name} at {url}, only found: {available_agents}."
            )
        elif name is None and len(available_agents) > 1:
            raise ValueError(
                f"There is more than one agent at {url} but provided name is {name}. Specify one of {available_agents}."
            )
        else:  # name is None and there is exactly one agent
            self._name = available_agents[0]

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

    def run(self, task: str) -> str:
        """BUG It assumes that the input parameter to the agent is always called `query`."""
        with MCPClientPool.get_connection(self.url, self.token) as mcp_client:
            try:
                answer = mcp_client.call_tool(self.name, {"query": task})
                return answer.content[0].text
            except Exception as e:
                print(f"Remote agent returned the following exception: \n{e}")
                raise e
