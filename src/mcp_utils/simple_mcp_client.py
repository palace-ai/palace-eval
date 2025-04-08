import asyncio
from typing import Dict, Optional

import nest_asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

# enable nested asyncio if running in jupyter notebook
try:
    from IPython import get_ipython

    if "IPKernelApp" in get_ipython().config:
        nest_asyncio.apply()
except Exception:
    pass  # not running in jupyter notebook


class SimpleMCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._streams_context = None
        self._session_context = None
        self._initialized = False

    def _run_async(self, coro):
        """Run an async coroutine in a way that preserves context"""
        try:
            # Get the current event loop if one exists
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # If no event loop exists in this thread, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(coro)

    def connect(
        self, url: str = "http://localhost:8080/sse", token: Optional[str] = None
    ):
        """Connect to the MCP server"""
        if not self._initialized:
            # Prepare headers if token is provided
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            # Create streams
            self._streams_context = sse_client(url=url, headers=headers)
            streams = self._run_async(self._streams_context.__aenter__())

            # Create and initialize session
            self._session_context = ClientSession(*streams)
            self.session = self._run_async(self._session_context.__aenter__())
            self._run_async(self.session.initialize())
            self._initialized = True

    def get_tools(self):
        """Get available tools"""
        if not self._initialized:
            raise RuntimeError("Client not initialized. Call connect first.")

        return self._run_async(self.session.list_tools())

    def call_tool(self, tool_name: str, parameters: Dict[str, str]):
        """Call a tool with parameters"""
        if not self._initialized:
            raise RuntimeError("Client not initialized. Call connect first.")

        return self._run_async(self.session.call_tool(tool_name, parameters))

    def cleanup(self):
        """Clean up resources.
        NOTE it may be bugged and the cleanup process may not complete.
        """
        if not self._initialized:
            return

        try:
            if self._session_context:
                self._run_async(self._session_context.__aexit__(None, None, None))
                self._session_context = None

            if self._streams_context:
                self._run_async(self._streams_context.__aexit__(None, None, None))
                self._streams_context = None
        finally:
            self._initialized = False
