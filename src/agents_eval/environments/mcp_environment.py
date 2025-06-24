from typing import List

from agents_eval.environments.base_environment import Environment
from agents_eval.mcp_utils.mcp_client import MCPClient
from agents_eval.tools import FinalAnswerTool, MCPTool, Tool
from agents_eval.utils.secrets import ALOHA_TOKEN


class MCPEnvironment(Environment):
    MCP_SERVERS = {
        "local": {"url": "http://localhost:8080/sse", "token": None},
        "aloha": {
            "url": "https://aloha-main-jrc-gpt.apps.ocpg.jrc.ec.europa.eu/api/mcp/jrc-gpt/sse",
            "token": ALOHA_TOKEN,
        },
    }

    def __init__(self, mcp_server: str):
        self._tools = None
        self.url = (
            __class__.MCP_SERVERS[mcp_server]["url"]
            if mcp_server in __class__.MCP_SERVERS  # if present, use alias
            else mcp_server  # otherwise, use direct URL
        )
        self.token = (
            __class__.MCP_SERVERS[mcp_server]["token"]
            if mcp_server in __class__.MCP_SERVERS
            else None
        )

    @property
    def name(self) -> str:
        """Return the name of the environment."""
        return f"MCP Environment @ {self.url}"

    @property
    def description(self) -> str:
        """Return the description of the environment."""
        return """This environment interfaces with an MCP server to pull the list of available tools and to execute the tools that you need. Therefore, the list is dynamic. I can't give you an overview of the available tools because at the time of writing this, there is not static list. Don't worry, the list of available tools will now be dynamically pulled and you will be able to see them."""

    @property
    def tools(self) -> List[Tool]:
        if self._tools is None:  # load tools the first time it's called
            with MCPClient().connection(url=self.url, token=self.token) as mcp_client:
                mcp_tools = (mcp_client.list_tools()).tools

            tools = []
            for mcp_tool in mcp_tools:
                tool_parameters = {
                    k: v["description"]
                    for k, v in mcp_tool.inputSchema["properties"].items()
                }
                required_parameters = mcp_tool.inputSchema["required"]
                tools.append(
                    MCPTool(
                        name=mcp_tool.name,
                        description=mcp_tool.description,
                        parameters=tool_parameters,
                        required_parameters=required_parameters,
                        server_url=self.url,
                        server_token=self.token,
                    )
                )

            # FinalAnswerTool should always be present. If it's not, add it
            if not any([tool.name == FinalAnswerTool().name for tool in tools]):
                tools.append(FinalAnswerTool())

            self._tools = tools

        return self._tools
