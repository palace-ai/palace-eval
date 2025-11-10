from typing import Optional

from palace.mcp_utils.mcp_client import MCPClientPool
from palace.tools import Tool
from palace.utils.exceptions import ToolHallucinationException


class MCPTool(Tool):
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, str],
        required_parameters: list[str],
        server_url: str,
        server_token: Optional[str] = None,
    ):
        self._name = name
        self._description = description
        self._parameters = parameters
        self._required_parameters = required_parameters
        self._server_url = server_url
        self._server_token = server_token

    def execute(self, **kwargs) -> str:
        """Execute the tool functionality."""
        # Check parameter compliance
        for parameter in self.required_parameters:
            if parameter not in kwargs:
                raise ToolHallucinationException(f"""Tool `{self.name}` encountered the following error: parameter `{parameter}` was not found in the tool call but it is required. Make sure to comply with the required parameters name and type. For this tool, the required parameters are the following:
{self.required_parameters}""")

        with MCPClientPool.get_connection(
            url=self._server_url, token=self._server_token
        ) as mcp_client:
            response = mcp_client.call_tool(self._name, kwargs)

        if response is None:
            return f"Tool `{self.name}` encountered some issue and returned no result, likely due to a timeout. Maybe it was unable to process your specific input, or there was some internal error."
        else:
            return response.content[
                0
            ].text[
                :300000
            ]  # TODO [:300000] is a workaround for very long outputs to ensure it fits in the model context

    @property
    def name(self) -> str:
        """Return the name of the tool."""
        return self._name

    @property
    def description(self) -> str:
        """Return the description of the tool."""
        return self._description

    @property
    def parameters(self) -> dict[str, str]:
        """Return the parameters that can be passed to the tool along with their description."""
        return self._parameters

    @property
    def required_parameters(self) -> list[str]:
        """Return the list of required parameters. By default, all of them are required. Override this method to define required ones."""
        return self._required_parameters
