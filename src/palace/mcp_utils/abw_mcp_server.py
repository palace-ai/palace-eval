import logging

import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import EmbeddedResource, ImageContent, TextContent
from mcp.types import Tool as MCPTool
from starlette.applications import Starlette
from starlette.routing import Route

from abw.mcp_servers.fetch_tool import FetchTool
from abw.mcp_servers.web_search_tool import WebSearchTool

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class MCPServer:
    server = Server("MCPServer")
    tools = [WebSearchTool(), FetchTool()]

    @server.list_tools()
    async def list_tools() -> list[MCPTool]:
        """
        Defines the tools available on this server, including parameter descriptions.
        This handler is called when the client requests the list of tools.
        """
        log.info("Client requested tool list.")
        return [
            MCPTool(
                name=tool.name,
                description=tool.description,
                inputSchema={
                    "type": "object",
                    "properties": {
                        k: {
                            "type": "string",
                            "description": v,
                        }
                        for k, v in tool.parameters.items()
                    },
                    "required": [k for k in tool.parameters],
                },
            )
            for tool in __class__.tools
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[TextContent | ImageContent | EmbeddedResource]:
        """
        Handles the actual execution request for a tool.
        This handler is called when the client invokes a specific tool.
        """
        log.info(f"Client called tool '{name}' with arguments: {arguments}")

        try:
            tool = [t for t in __class__.tools if t.name == name][0]

        except IndexError as e:
            print(f"Can't find a tool matching {name} in {__class__.tools}:\n{e}")

        result = tool.execute(**arguments)

        return [TextContent(type="text", text=result)]

    def start(
        self, host: str = "0.0.0.0", port: int = 8080, debug: bool = False
    ) -> None:
        """Create a Starlette application that can serve the provided mcp server with SSE."""

        sse = SseServerTransport("/messages/")

        class SSEEndpoint:
            def __init__(self, sse, server):
                self.sse = sse
                self.server = server

            async def __call__(self, scope, receive, send):
                assert scope["type"] == "http"
                log.info(f"SSE connection request received from {scope.get('client')}")
                async with self.sse.connect_sse(scope, receive, send) as (
                    read_stream,
                    write_stream,
                ):
                    log.info("SSE transport connected, starting MCP server run loop.")
                    try:
                        init_options = self.server.create_initialization_options()
                        await self.server.run(read_stream, write_stream, init_options)
                    except Exception:
                        log.exception("Exception during mcp_server.run")
                    finally:
                        log.info("MCP server run loop finished.")

        starlette_app = Starlette(
            debug=debug,
            routes=[Route("/sse", endpoint=SSEEndpoint(sse, __class__.server))],
            on_startup=[lambda: log.info("Starlette server starting...")],
            on_shutdown=[lambda: log.info("Starlette server shutting down...")],
        )
        starlette_app.mount("/messages/", app=sse.handle_post_message)
        uvicorn.run(starlette_app, host=host, port=port)
        log.info(f"Starting Uvicorn server on port {port}")
