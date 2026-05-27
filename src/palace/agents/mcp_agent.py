import json
from typing import Any, Callable

from mcp.types import CallToolResult, TextContent
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from palace.agents import Agent
from palace.evaluation.types import AgentResult
from palace.mcp_utils.mcp_client import list_tools, _call_tool


class MCPAgent(Agent):
    """Agent that connects to a remote MCP server."""

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
            url: The URL of the MCP server.
            token: Authentication token for the MCP server.
            name: Name of the agent/tool to connect to.
            params: Custom parameters to pass to the agent/tool.
            output_processor: Function to process the agent/tool output.
        """
        self.url = url
        self.token = token
        self.params = params
        self.output_processor = output_processor

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
        else:
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
                    f"Can't find the input parameter for the agent {self._name} at {url}."
                ) from e

    @property
    def name(self) -> str:
        return self._name

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=5, max=60),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    )
    async def _run_with_retry(self, task: str) -> AgentResult:
        params = {self._input_parameter: task}
        if self.params is not None and "custom" in self.params:
            params |= self.params["custom"]

        output: CallToolResult = await _call_tool(self.url, self.name, params, self.token)

        if self.output_processor is not None:
            answer = self.output_processor(output)
        else:
            if not isinstance(output.content[0], TextContent):
                raise ValueError(
                    f"MCPAgent expected TextContent, got: {type(output.content[0])}"
                )
            answer = output.content[0].text
            if not isinstance(answer, str) or answer.strip() == "":
                raise ValueError(
                    f"MCPAgent answer not found in output content. Got: {output.content}"
                )

        try:
            assert isinstance(output.content[1], TextContent)
            metrics = json.loads(output.content[1].text)
            assert isinstance(metrics, dict)
        except Exception:
            metrics = None

        return AgentResult(answer=answer, metrics=metrics)

    async def run(self, prompt: str, image: str | None = None, *, task_id: str | None = None) -> AgentResult:
        if image is not None:
            raise NotImplementedError("MCPAgent does not support image attachments yet")
        return await self._run_with_retry(prompt)
