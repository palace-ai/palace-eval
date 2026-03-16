import argparse

from palace.mcp_utils.mcp_server import MCPServerSHTTP


def main():
    parser = argparse.ArgumentParser(
        description="Run MCP server with streamable HTTP transport"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    mcp_server = MCPServerSHTTP()
    mcp_server.start(args.host, args.port)
