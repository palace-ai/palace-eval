import logging

import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import EmbeddedResource, ImageContent, TextContent, Tool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route

from palace.environments.base_environment import Environment
from palace.environments.custom_environment import CustomEnvironment
from palace.tools import FetchTool, WebSearchTool

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class MCPServer:
    server = Server("MCPServer")
    tool_environment: Environment = CustomEnvironment([WebSearchTool(), FetchTool()])

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """
        Defines the tools available on this server, including parameter descriptions.
        This handler is called when the client requests the list of tools.
        """
        log.info("Client requested tool list.")
        return [
            Tool(
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
            for tool in __class__.tool_environment.tools
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
            tool = [t for t in __class__.tool_environment.tools if t.name == name][0]

        except IndexError as e:
            print(
                f"Can't find a tool matching {name} in {__class__.tool_environment.tools}:\n{e}"
            )

        result = tool.execute(**arguments)

        return [TextContent(type="text", text=result)]

    def start(
        self, host: str = "0.0.0.0", port: int = 8080, debug: bool = False
    ) -> None:
        """Create a Starlette application that can serve the provided mcp server with SSE."""
        sse = SseServerTransport("/messages/")

        async def handle_sse(request: Request) -> None:
            log.info(f"SSE connection request received from {request.client}")
            async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,
            ) as (read_stream, write_stream):
                log.info("SSE transport connected, starting MCP server run loop.")
                try:
                    init_options = self.server.create_initialization_options()

                    await self.server.run(
                        read_stream,
                        write_stream,
                        init_options,
                    )
                except Exception:
                    log.exception("Exception during mcp_server.run")
                finally:
                    log.info("MCP server run loop finished.")

        starlette_app = Starlette(
            debug=debug,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
            on_startup=[lambda: log.info("Starlette server starting...")],
            on_shutdown=[lambda: log.info("Starlette server shutting down...")],
        )

        uvicorn.run(starlette_app, host=host, port=port)

    # def create_starlette_app(
    #     mcp_server_instance: Server, *, debug: bool = False
    # ) -> Starlette:
    #     """Create a Starlette application that can serve the provided mcp server with SSE."""
    #     sse = SseServerTransport("/messages/")

    #     async def handle_sse(request: Request) -> None:
    #         log.info(f"SSE connection request received from {request.client}")
    #         async with sse.connect_sse(
    #             request.scope,
    #             request.receive,
    #             request._send,
    #         ) as (read_stream, write_stream):
    #             log.info("SSE transport connected, starting MCP server run loop.")
    #             try:
    #                 init_options = mcp_server_instance.create_initialization_options()

    #                 await mcp_server_instance.run(
    #                     read_stream,
    #                     write_stream,
    #                     init_options,
    #                 )
    #             except Exception:
    #                 log.exception("Exception during mcp_server.run")
    #             finally:
    #                 log.info("MCP server run loop finished.")

    #     return Starlette(
    #         debug=debug,
    #         routes=[
    #             Route("/sse", endpoint=handle_sse),
    #             Mount("/messages/", app=sse.handle_post_message),
    #         ],
    #         on_startup=[lambda: log.info("Starlette server starting...")],
    #         on_shutdown=[lambda: log.info("Starlette server shutting down...")],
    #     )
