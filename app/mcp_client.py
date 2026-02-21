from fastmcp import Client
from fastmcp.exceptions import ToolError

from app.config import settings

_client = Client(settings.MCP_SERVER_URL)
_tools_cache: list | None = None


async def call_tool(name: str, arguments: dict) -> str:
    """Call an MCP tool and return the text result."""
    async with _client:
        try:
            result = await _client.call_tool(name, arguments)
        except ToolError as e:
            return f"Error: {e}"
        if result.is_error:              # defensive fallback
            return f"Error: {result.content[0].text}"
        return result.content[0].text


async def get_tools() -> list:
    """List available MCP tools. Cached after first call (server declares listChanged: false)."""
    global _tools_cache
    if _tools_cache is not None:
        return _tools_cache
    async with _client:
        _tools_cache = await _client.list_tools()
    return _tools_cache


def clear_tools_cache():
    """Clear the cached tools list (useful for testing)."""
    global _tools_cache
    _tools_cache = None
