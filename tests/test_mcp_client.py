"""Tests for app.mcp_client — all MCP calls mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError

from app.mcp_client import call_tool, get_tools, clear_tools_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_tools_cache()
    yield
    clear_tools_cache()


def _make_result(text, is_error=False):
    """Create a mock MCP tool result."""
    content_item = MagicMock()
    content_item.text = text
    result = MagicMock()
    result.content = [content_item]
    result.is_error = is_error
    return result


@pytest.mark.asyncio
async def test_call_tool_success():
    mock_client = AsyncMock()
    mock_client.call_tool.return_value = _make_result("Found 40 products")

    with patch("app.mcp_client._client", mock_client):
        result = await call_tool("search_products", {"query": "monitor"})

    assert result == "Found 40 products"


@pytest.mark.asyncio
async def test_call_tool_error():
    mock_client = AsyncMock()
    mock_client.call_tool.return_value = _make_result(
        "Customer not found or PIN incorrect", is_error=True
    )

    with patch("app.mcp_client._client", mock_client):
        result = await call_tool("verify_customer_pin", {"email": "x", "pin": "0000"})

    assert result.startswith("Error:")
    assert "Customer not found" in result


@pytest.mark.asyncio
async def test_call_tool_tool_error_exception():
    """ToolError raised by fastmcp is caught and returned as error string."""
    mock_client = AsyncMock()
    mock_client.call_tool.side_effect = ToolError("Customer not found or PIN incorrect")

    with patch("app.mcp_client._client", mock_client):
        result = await call_tool("verify_customer_pin", {"email": "bad@bad.com", "pin": "0000"})

    assert result.startswith("Error:")
    assert "Customer not found" in result


@pytest.mark.asyncio
async def test_get_tools_returns_list():
    mock_tool = MagicMock()
    mock_tool.name = "list_products"

    mock_client = AsyncMock()
    mock_client.list_tools.return_value = [mock_tool]

    with patch("app.mcp_client._client", mock_client):
        tools = await get_tools()

    assert len(tools) == 1
    assert tools[0].name == "list_products"


@pytest.mark.asyncio
async def test_get_tools_caches():
    mock_tool = MagicMock()
    mock_tool.name = "list_products"

    mock_client = AsyncMock()
    mock_client.list_tools.return_value = [mock_tool]

    with patch("app.mcp_client._client", mock_client):
        await get_tools()
        await get_tools()

    # list_tools should only be called once due to caching
    assert mock_client.list_tools.call_count == 1
