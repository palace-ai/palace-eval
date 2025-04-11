from typing import Dict, List, Optional

from mcp_utils.mcp_client import MCPClientV3

from . import Tool


class RemoteTool(Tool):
    def __init__(
        self, name: str, description: str, parameters: Dict[str, str], required_parameters: List[str], server_url: str, server_token: Optional[str] = None
    ):
        self._name = name
        self._description = description
        self._parameters = parameters
        self._required_parameters = required_parameters
        self._server_url = server_url
        self._server_token = server_token
        # self._mcp_client = MCPClientV3()

    def execute(self, **kwargs) -> str:
        """Execute the tool functionality."""
        # Check parameter compliance
        for parameter in self.required_parameters:
            if parameter not in kwargs:
                return f"""Tool `{self.name}` encountered the following error: parameter `{parameter}` was not found in the tool call but it is required. Make sure to comply with the required parameters name and type. For this tool, the required parameters are the following:
{self.required_parameters}"""
            
        with MCPClientV3().connection(url=self._server_url, token=self._server_token) as mcp_client:
            response = mcp_client.call_tool(self._name, kwargs)
        # self._mcp_client.connect(url=self._server_url, token=self._server_token)
        # response = self._mcp_client.call_tool(self._name, kwargs)
        return response.content[0].text

    @property
    def name(self) -> str:
        """Return the name of the tool."""
        return self._name

    @property
    def description(self) -> str:
        """Return the description of the tool."""
        return self._description

    @property
    def parameters(self) -> Dict[str, str]:
        """Return the parameters that can be passed to the tool along with their description."""
        return self._parameters

    @property
    def required_parameters(self) -> List[str]:
        """Return the list of required parameters. By default, all of them are required. Override this method to define required ones."""
        return self._required_parameters