import argparse
import logging

import environments
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import EmbeddedResource, ImageContent, TextContent, Tool

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

SERVER_NAME = "MCPServer"
mcp_server = Server(SERVER_NAME)
agent_environment: environments.Environment = (
    environments.IsolatedEnvironmentWithInterpreter()
)


@mcp_server.list_tools()
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
        for tool in agent_environment.tools
    ]


@mcp_server.call_tool()
async def call_tool(
    name: str, arguments: dict
) -> list[TextContent | ImageContent | EmbeddedResource]:
    """
    Handles the actual execution request for a tool.
    This handler is called when the client invokes a specific tool.
    """
    log.info(f"Client called tool '{name}' with arguments: {arguments}")

    try:
        tool = [t for t in agent_environment.tools if t.name == name][0]

    except IndexError as e:
        print(f"Can't find a tool matching {name} in {agent_environment.tools}:\n{e}")

    result = tool.execute(**arguments)

    return [TextContent(type="text", text=result)]


def create_starlette_app(
    mcp_server_instance: Server, *, debug: bool = False
) -> Starlette:
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
                init_options = mcp_server_instance.create_initialization_options()

                await mcp_server_instance.run(
                    read_stream,
                    write_stream,
                    init_options,
                )
            except Exception:
                log.exception("Exception during mcp_server.run")
            finally:
                log.info("MCP server run loop finished.")

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        on_startup=[lambda: log.info("Starlette server starting...")],
        on_shutdown=[lambda: log.info("Starlette server shutting down...")],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run MCP SSE-based server using low-level API"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    log.info(f"Creating Starlette app for MCP server '{SERVER_NAME}'")
    starlette_app = create_starlette_app(mcp_server, debug=True)

    log.info(f"Starting Uvicorn server on {args.host}:{args.port}")
    uvicorn.run(starlette_app, host=args.host, port=args.port)
