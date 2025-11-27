import json
from typing import Any

from mcp.types import CallToolResult, TextContent
from tenacity import retry, stop_after_attempt, wait_fixed

from palace.agents import Agent
from palace.environments.base_environment import Environment
from palace.environments.unknown_environment import UnknownEnvironment
from palace.mcp_utils.mcp_client import MCPClientPool


class MCPAgent(Agent):
    """A class to connect to a remote agent deployed via MCP and call it as a black box."""

    def __init__(self, url: str, token: str | None = None, name: str | None = None):
        self.url = url
        self.token = token
        self._environment = UnknownEnvironment()

        with MCPClientPool.get_connection(url, token) as mcp_client:
            available_agents = mcp_client.list_tools().tools

        if len(available_agents) == 0:
            raise ValueError(f"There is no agent or tool at {url}.")

        if name is not None and name in [a.name for a in available_agents]:
            self._name = name
        elif name is not None and name not in [a.name for a in available_agents]:
            raise ValueError(
                f"There is no agent with the provided name {name} at {url}, only found: {available_agents}."
            )
        elif name is None and len(available_agents) > 1:
            raise ValueError(
                f"There is more than one agent at {url} but provided name is {name}. Specify one of {available_agents}."
            )
        else:  # name is None and there is exactly one agent
            self._name = available_agents[0].name

        try:
            self._input_parameter = list(
                [a for a in available_agents if a.name == self._name][0]
                .inputSchema["properties"]
                .keys()
            )[0]
        except Exception as e:
            raise ValueError(
                f"Can't find the input parameter for the agent {self._name} at {url}. \
                    Are you sure the agent has an inputSchema={{'properties': ...}} defined?"
            ) from e

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

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_fixed(5),
        before_sleep=lambda retry_state: print(
            "Remote agent raised an exception, retrying...",
        ),
    )
    def _run_with_retry(self, task: str) -> tuple[str, dict[str, Any] | None]:
        """Run the agent with retries on failure."""
        with MCPClientPool.get_connection(self.url, self.token) as mcp_client:
            try:
                print(f"Calling remote agent {self.name} with task: {task}")
                output: CallToolResult = mcp_client.call_tool(
                    self.name, {self._input_parameter: task}
                )
            except Exception as e:
                print(f"Remote agent returned the following exception: \n{e}")
                raise e

        try:
            assert isinstance(output.content[0], TextContent)
            answer = output.content[0].text
            assert isinstance(answer, str) and answer.strip() != ""
        except Exception:
            raise ValueError(
                f"MCPAgent answer not found in output content. Got: {output.content}"
            )

        try:
            assert isinstance(output.content[1], TextContent)
            metrics = json.loads(output.content[1].text)
            assert isinstance(metrics, dict)
        except Exception:
            metrics = None

        return answer, metrics

    def run(self, task: str) -> tuple[str, dict[str, Any] | None]:
        return self._run_with_retry(task)
