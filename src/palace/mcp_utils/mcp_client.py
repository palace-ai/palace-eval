"""Simple MCP client using official SDK with streamable HTTP transport."""

import asyncio
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, ListToolsResult

DEFAULT_TIMEOUT = 5
DEFAULT_READ_TIMEOUT = 300


def list_tools(
    url: str, token: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT
) -> ListToolsResult:
    """List available tools from an MCP server."""
    return asyncio.run(_list_tools(url, token, timeout))


def call_tool(
    url: str,
    tool_name: str,
    arguments: dict[str, Any],
    token: Optional[str] = None,
    timeout: float = DEFAULT_READ_TIMEOUT,
) -> CallToolResult:
    """Call a tool on an MCP server."""
    return asyncio.run(_call_tool(url, tool_name, arguments, token, timeout))


async def _list_tools(
    url: str, token: Optional[str], timeout: float
) -> ListToolsResult:
    headers = {"Authorization": f"Bearer {token}"} if token else None
    async with streamablehttp_client(url, headers=headers, timeout=timeout) as (
        read,
        write,
        _,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.list_tools()


async def _call_tool(
    url: str,
    tool_name: str,
    arguments: dict[str, Any],
    token: Optional[str],
    timeout: float,
) -> CallToolResult:
    headers = {"Authorization": f"Bearer {token}"} if token else None
    async with streamablehttp_client(
        url, headers=headers, sse_read_timeout=timeout
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)
