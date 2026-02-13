import argparse

from palace.mcp_utils.mcp_server import MCPServer


def main():
    parser = argparse.ArgumentParser(
        description="Run MCP SSE-based server using low-level API"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    mcp_server = MCPServer()
    mcp_server.start(args.host, args.port)
