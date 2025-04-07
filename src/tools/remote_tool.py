from typing import Dict

from mcp_utils.simple_mcp_client import SimpleMCPClient

from . import Tool


class RemoteTool(Tool):
    def __init__(
        self, name: str, description: str, parameters: Dict[str, str], server_url: str
    ):
        self._name = name
        self._description = description
        self._parameters = parameters
        self._server_url = server_url

        self._mcp_client = SimpleMCPClient()

    def execute(self, **kwargs) -> str:
        """Execute the tool functionality."""
        # Check parameter compliance
        for parameter in self.parameters:
            if parameter not in kwargs:
                return f"""Tool `{self.name}` encountered the following error: parameter `{parameter}` was not found in the tool call. Make sure to comply with the required parameters name and type. For this tool, the required parameters are the following:
{self.parameters}"""

        self._mcp_client.connect(self._server_url)
        response = self._mcp_client.call_tool(self._name, kwargs)
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
        """Return the parameters required by the tool along with their description."""
        return self._parameters
