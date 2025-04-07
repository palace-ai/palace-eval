from typing import List

import tools
from mcp_utils.simple_mcp_client import SimpleMCPClient
from tools import RemoteTool

from . import Environment


class MCPEnvironment(Environment):
    def __init__(self, url="http://localhost:8080/sse"):
        self._tools = None
        self.url = url

        self.mcp_client = SimpleMCPClient()

    @property
    def name(self) -> str:
        """Return the name of the environment."""
        return "MCP Environment"

    @property
    def description(self) -> str:
        """Return the description of the environment."""
        return """This environment interfaces with an MCP server to pull the list of available tools and to execute the tools that you need. Therefore, the list is dynamic. I can't give you an overview of the available tools because at the time of writing this, there is not static list. Don't worry, the list of available tools will now be dynamically pulled and you will be able to see them."""

    @property
    def tools(self) -> List[tools.Tool]:
        if self._tools is None:  # load tools the first time it's called
            self.mcp_client.connect(url=self.url)
            mcp_tools = (self.mcp_client.get_tools()).tools
            tools = []
            for mcp_tool in mcp_tools:
                tool_parameters = {
                    k: v["description"]
                    for k, v in mcp_tool.inputSchema["properties"].items()
                }
                print(tool_parameters)
                tools.append(
                    RemoteTool(
                        name=mcp_tool.name,
                        description=mcp_tool.description,
                        parameters=tool_parameters,
                        server_url=self.url,
                    )
                )
            self._tools = tools

        return self._tools
