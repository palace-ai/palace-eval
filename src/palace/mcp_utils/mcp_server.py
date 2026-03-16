import asyncio
import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager

import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.types import EmbeddedResource, ImageContent, TextContent, Tool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route

from palace.environments.base_environment import Environment
from palace.environments.custom_environment import CustomEnvironment
from palace.tools import FetchTool, WebSearchTool

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class BaseMCPServer(ABC):
    """Base class for MCP servers with shared tool registration logic."""

    def __init__(self, name: str = "MCPServer"):
        self.server = Server(name)
        self.tool_environment: Environment = CustomEnvironment([WebSearchTool(), FetchTool()])
        self._register_handlers()

    def _register_handlers(self):
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            log.info("Client requested tool list.")
            return [
                Tool(
                    name=tool.name,
                    description=tool.description,
                    inputSchema={
                        "type": "object",
                        "properties": {
                            k: {"type": "string", "description": v}
                            for k, v in tool.parameters.items()
                        },
                        "required": [k for k in tool.parameters],
                    },
                )
                for tool in self.tool_environment.tools
            ]

        @self.server.call_tool()
        async def call_tool(
            name: str, arguments: dict
        ) -> list[TextContent | ImageContent | EmbeddedResource]:
            log.info(f"Client called tool '{name}' with arguments: {arguments}")
            try:
                tool = [t for t in self.tool_environment.tools if t.name == name][0]
                result = tool.execute(**arguments)
                return [TextContent(type="text", text=result)]
            except IndexError as e:
                log.error(f"Tool '{name}' not found in {self.tool_environment.tools}")
                raise e

    @abstractmethod
    def start(self, host: str = "0.0.0.0", port: int = 8080, debug: bool = False) -> None:
        pass


class MCPServerSSE(BaseMCPServer):
    """MCP server using SSE transport (legacy)."""

    def start(self, host: str = "0.0.0.0", port: int = 8080, debug: bool = False) -> None:
        sse = SseServerTransport("/messages/")

        async def handle_sse(request: Request) -> None:
            log.info(f"SSE connection from {request.client}")
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options(),
                )

        app = Starlette(
            debug=debug,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )
        uvicorn.run(app, host=host, port=port)


class MCPServerSHTTP(BaseMCPServer):
    """MCP server using streamable HTTP transport."""

    def start(self, host: str = "0.0.0.0", port: int = 8080, debug: bool = False) -> None:
        transport = StreamableHTTPServerTransport(mcp_session_id=None)
        server = self.server

        async def run_server():
            async with transport.connect() as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )

        @asynccontextmanager
        async def lifespan(app):
            task = asyncio.create_task(run_server())
            yield
            task.cancel()

        async def mcp_asgi(scope, receive, send):
            await transport.handle_request(scope, receive, send)

        app = Starlette(
            debug=debug,
            lifespan=lifespan,
            routes=[Mount("/mcp", app=mcp_asgi)],
        )
        uvicorn.run(app, host=host, port=port)


# Backward compatibility alias
MCPServer = MCPServerSSE
