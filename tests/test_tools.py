"""Tests for app.tools — schema conversion and classification."""

from unittest.mock import MagicMock

from app.tools import (
    mcp_tool_to_openai,
    convert_all_tools,
    is_public,
    requires_auth,
    is_write_tool,
    PUBLIC_TOOLS,
    AUTH_REQUIRED_TOOLS,
    WRITE_TOOLS,
)


def _make_mcp_tool(name="list_products", desc="List products", schema=None):
    tool = MagicMock()
    tool.name = name
    tool.description = desc
    tool.inputSchema = schema or {"type": "object", "properties": {}}
    return tool


def test_mcp_tool_to_openai_format():
    tool = _make_mcp_tool(
        name="search_products",
        desc="Search products",
        schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    )
    result = mcp_tool_to_openai(tool)

    assert result["type"] == "function"
    assert result["function"]["name"] == "search_products"
    assert result["function"]["description"] == "Search products"
    assert "query" in result["function"]["parameters"]["properties"]


def test_convert_all_tools():
    tools = [_make_mcp_tool(f"tool_{i}") for i in range(3)]
    result = convert_all_tools(tools)
    assert len(result) == 3
    assert all(r["type"] == "function" for r in result)


def test_public_tools():
    for name in ["list_products", "get_product", "search_products", "verify_customer_pin"]:
        assert is_public(name)
    for name in ["get_customer", "list_orders", "get_order", "create_order"]:
        assert not is_public(name)


def test_auth_required_tools():
    for name in ["get_customer", "list_orders", "get_order", "create_order"]:
        assert requires_auth(name)
    for name in ["list_products", "get_product", "search_products", "verify_customer_pin"]:
        assert not requires_auth(name)


def test_write_tools():
    assert is_write_tool("create_order")
    assert not is_write_tool("list_orders")
    assert not is_write_tool("get_product")


def test_all_tools_classified():
    all_tools = PUBLIC_TOOLS | AUTH_REQUIRED_TOOLS
    expected = {
        "list_products", "get_product", "search_products", "verify_customer_pin",
        "get_customer", "list_orders", "get_order", "create_order",
    }
    assert all_tools == expected


def test_write_tools_subset_of_auth():
    assert WRITE_TOOLS.issubset(AUTH_REQUIRED_TOOLS)
