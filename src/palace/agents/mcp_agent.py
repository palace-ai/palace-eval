import json
from typing import Any, Callable

from mcp.types import CallToolResult, TextContent
from tenacity import retry, stop_after_attempt, wait_fixed

from palace.agents import Agent
from palace.environments.base_environment import Environment
from palace.environments.unknown_environment import UnknownEnvironment
from palace.mcp_utils.mcp_client import call_tool, list_tools


class MCPAgent(Agent):
    """A class to connect to a remote agent deployed via MCP and call it as a black box."""

    def __init__(
        self,
        url: str,
        token: str | None = None,
        name: str | None = None,
        params: dict[str, Any] | None = None,
        output_processor: Callable[[CallToolResult], str] | None = None,
    ):
        """Initialize the MCPAgent.

        Args:
            url (str): The URL of the MCP server where the agent is deployed.
            token (str | None): The authentication token for the MCP server.
            name (str | None): The name of the agent/tool to connect to. If None, and there is only one agent/tool available, it will be used.
            params (dict[str, Any] | None): Custom parameters to pass to the agent/tool. If None, the first input parameter defined in the agent's input schema will be used. Valid keys are "main" for the name of the main input parameter, and "custom" for any additional parameters.
            output_processor (Callable[[CallToolResult], str] | None): A function to process the output of the agent/tool call. If None, the first text content of the output will be used as the answer.

        Raises:
            ValueError: If no agents/tools are found at the given URL, or if the specified name is not found, or if multiple agents/tools are found but no name is provided.
        """
        self.url = url
        self.token = token
        self.params = params
        self.output_processor = output_processor
        self._environment = UnknownEnvironment()

        available_agents = list_tools(url, token).tools

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

        if self.params is not None and "main" in self.params:
            self._input_parameter = self.params["main"]
        else:
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

        params = {self._input_parameter: task}
        if self.params is not None and "custom" in self.params:
            params |= self.params["custom"]

        try:
            output: CallToolResult = call_tool(self.url, self.name, params, self.token)
        except Exception as e:
            print(f"Remote agent returned the following exception: \n{e}")
            raise e

        if self.output_processor is not None:
            try:
                answer = self.output_processor(output)
            except Exception:
                print(
                    f"[bold][red]Error while applying output_processor '{self.output_processor}':"
                )
                raise
        else:
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

    def run(self, prompt: str, image: str | None = None) -> tuple[str, dict[str, Any] | None]:
        if image is not None:
            raise NotImplementedError("MCPAgent does not support image attachments yet")
        return self._run_with_retry(prompt)
