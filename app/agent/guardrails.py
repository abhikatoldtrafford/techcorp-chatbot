"""Pre-call, post-call, and loop guardrails for the agent."""

import re

from app.tools import requires_auth, is_write_tool
from app.agent.state import ConversationState


# ---------------------------------------------------------------------------
# Pre-call guard
# ---------------------------------------------------------------------------

def check_tool_allowed(
    tool_name: str, arguments: dict, state: ConversationState
) -> tuple[bool, str]:
    """Check if a tool call is allowed given current state.

    Returns (allowed: bool, reason: str). If not allowed, reason explains why.
    """
    # Auth-required tools blocked when not authenticated
    if requires_auth(tool_name) and not state.is_authenticated:
        return False, (
            "Customer not verified. Please ask the customer for their "
            "email and 4-digit PIN before accessing account data."
        )

    # For auth-required tools, enforce customer_id matches state
    if requires_auth(tool_name) and state.is_authenticated:
        arg_cid = arguments.get("customer_id")
        if arg_cid and arg_cid != state.customer_id:
            return False, "You can only access data for the currently verified customer."
        if not arg_cid and tool_name in ("list_orders", "get_customer"):
            return False, f"Missing customer_id. Use the verified customer_id: {state.customer_id}"

    # Write tools need user confirmation in chat history
    if is_write_tool(tool_name):
        if not _user_confirmed_order(state.messages):
            return False, (
                "You must present an order summary and get explicit confirmation "
                "from the customer before placing an order."
            )

    return True, ""


def _user_confirmed_order(messages: list[dict]) -> bool:
    """Check if the user confirmed an order in recent messages."""
    confirmation_patterns = re.compile(
        r"\b(yes|yep|yeah|yea|confirm|confirmed|go ahead|place it|do it|"
        r"approved|approve|sure|ok|okay|absolutely|please|proceed|"
        r"sounds good|let's do it|that's right|correct|affirmative|place the order)\b",
        re.IGNORECASE,
    )
    # Look at the last few user messages for confirmation
    for msg in reversed(messages[-6:]):
        if msg.get("role") == "user":
            if confirmation_patterns.search(msg.get("content", "")):
                return True
            # If we hit a user message that isn't a confirmation, stop
            break
    return False


# ---------------------------------------------------------------------------
# Auto-fix arguments: inject customer_id when missing
# ---------------------------------------------------------------------------

def auto_fix_arguments(
    tool_name: str, arguments: dict, state: ConversationState
) -> dict:
    """Auto-inject customer_id for auth-required tools when the LLM forgets it."""
    if (
        requires_auth(tool_name)
        and state.is_authenticated
        and "customer_id" not in arguments
        and tool_name in ("list_orders", "get_customer", "create_order")
    ):
        arguments = {**arguments, "customer_id": state.customer_id}
    return arguments


# ---------------------------------------------------------------------------
# Post-call guard
# ---------------------------------------------------------------------------

def process_tool_result(
    tool_name: str, result: str, state: ConversationState
) -> str:
    """Process a tool result, potentially updating state. Returns the (possibly truncated) result."""
    # After successful verify_customer_pin, extract customer info and update state
    if tool_name == "verify_customer_pin" and not result.startswith("Error"):
        _extract_customer_info(result, state)

    # Truncate very long results
    max_len = 4000
    if len(result) > max_len:
        truncated = result[:max_len]
        # Try to cut at a line boundary
        last_newline = truncated.rfind("\n")
        if last_newline > max_len // 2:
            truncated = truncated[:last_newline]
        return truncated + "\n\n... (results truncated, showing partial list)"

    return result


def _extract_customer_info(result: str, state: ConversationState):
    """Parse verify_customer_pin result and update state."""
    # Expected format:
    # ✓ Customer verified: Donald Garcia
    # Customer ID: 41c2903a-...
    # Email: donaldgarcia@example.net
    # Role: admin

    name_match = re.search(r"Customer verified:\s*(.+)", result)
    id_match = re.search(r"Customer ID:\s*(\S+)", result)
    email_match = re.search(r"Email:\s*(\S+)", result)

    if id_match:
        state.is_authenticated = True
        state.customer_id = id_match.group(1)
    if name_match:
        state.customer_name = name_match.group(1).strip()
    if email_match:
        state.customer_email = email_match.group(1).strip()


# ---------------------------------------------------------------------------
# Loop guard
# ---------------------------------------------------------------------------

def check_loop_limit(tool_call_count: int, max_calls: int) -> tuple[bool, str]:
    """Check if the tool call loop has exceeded the limit."""
    if tool_call_count >= max_calls:
        return False, (
            f"Tool call limit reached ({max_calls} calls this turn). "
            "Please provide a response to the customer."
        )
    return True, ""
