from typing import List

from mcp_utils.mcp_client import MCPClient
from tools import RemoteTool, FinalAnswerTool, Tool

from . import Environment
from typing import Optional

class MCPEnvironment(Environment):

    MCP_SERVERS = {
        "local": {
            "url": "http://localhost:8080/sse", 
            "token": None
        }, 
        "aloha": {
            "url": "https://aloha-main-jrc-gpt.apps.ocpg.jrc.ec.europa.eu/api/mcp/jrc-gpt/sse", 
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbklkIjoiNjdmNTFmZDU1ODQ0ZTExMjIwZjVlMzc4Iiwic3ViIjoiNjdmM2FmMjZiMjg3OWJiNjFiYTU1NTU2IiwiY2xhaW1zIjpbIk1DUF9QUk9YWV9BQ0NFU1MiXSwiZXhwaXJhdGlvbkRhdGUiOiJXZWQsIDMxIERlYyAyMDI1IDAwOjAwOjAwIEdNVCIsImlhdCI6MTc0NDExNzcxN30.DvTUESGeyGeLVgWb9Sr0YKyPbNlAzf1oMEmfkWHPx9Q"
        }
    }
    def __init__(self, mcp_server: Optional[str]="local"):
        self._tools = None
        self.url = __class__.MCP_SERVERS[mcp_server]["url"]
        self.token = __class__.MCP_SERVERS[mcp_server]["token"]

        self.mcp_client = MCPClient()

    @property
    def name(self) -> str:
        """Return the name of the environment."""
        return "MCP Environment"

    @property
    def description(self) -> str:
        """Return the description of the environment."""
        return """This environment interfaces with an MCP server to pull the list of available tools and to execute the tools that you need. Therefore, the list is dynamic. I can't give you an overview of the available tools because at the time of writing this, there is not static list. Don't worry, the list of available tools will now be dynamically pulled and you will be able to see them."""

    @property
    def tools(self) -> List[Tool]:
        if self._tools is None:  # load tools the first time it's called
            self.mcp_client.connect(url=self.url, token=self.token)
            mcp_tools = (self.mcp_client.get_tools()).tools
            tools = [FinalAnswerTool()]  # FinalAnswerTool should always be present
            for mcp_tool in mcp_tools:
                tool_parameters = {
                    k: v["description"]
                    for k, v in mcp_tool.inputSchema["properties"].items()
                }
                required_parameters = mcp_tool.inputSchema["required"]
                print(tool_parameters)
                tools.append(
                    RemoteTool(
                        name=mcp_tool.name,
                        description=mcp_tool.description,
                        parameters=tool_parameters,
                        required_parameters=required_parameters,
                        server_url=self.url,
                        server_token=self.token,
                    )
                )

            self._tools = tools

        return self._tools
