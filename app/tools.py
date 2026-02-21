"""MCP-to-OpenAI schema converter and tool classification."""

PUBLIC_TOOLS = {"list_products", "get_product", "search_products", "verify_customer_pin"}
AUTH_REQUIRED_TOOLS = {"get_customer", "list_orders", "get_order", "create_order"}
WRITE_TOOLS = {"create_order"}


def mcp_tool_to_openai(tool) -> dict:
    """Convert a single MCP tool to OpenAI function-calling format."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema,
        },
    }


def convert_all_tools(mcp_tools: list) -> list[dict]:
    """Convert a list of MCP tools to OpenAI function-calling format."""
    return [mcp_tool_to_openai(t) for t in mcp_tools]


def is_public(tool_name: str) -> bool:
    return tool_name in PUBLIC_TOOLS


def requires_auth(tool_name: str) -> bool:
    return tool_name in AUTH_REQUIRED_TOOLS


def is_write_tool(tool_name: str) -> bool:
    return tool_name in WRITE_TOOLS
