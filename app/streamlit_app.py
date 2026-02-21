"""Streamlit UI for TechCorp Customer Support chatbot (direct mode — no FastAPI needed).

Run with:  streamlit run app/streamlit_app.py
"""

import asyncio
import os
import queue
import sys
import threading
from datetime import datetime

# Ensure project root is on sys.path so `from app.…` imports work
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st

from app.agent.state import ConversationState
from app.agent.chat import chat, TokenEvent, ToolCallEvent, ToolResultEvent
from app.mcp_client import get_tools

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TOOL_DISPLAY_NAMES = {
    "list_products": "Browsing products",
    "get_product": "Getting product details",
    "search_products": "Searching products",
    "verify_customer_pin": "Verifying identity",
    "get_customer": "Loading customer profile",
    "list_orders": "Loading orders",
    "get_order": "Getting order details",
    "create_order": "Placing order",
}

_SENTINEL = object()

WELCOME_MESSAGE = (
    "Welcome to **TechCorp Customer Support**! I can help you with:\n\n"
    "- **Browse products** — search our catalog of computers, monitors, "
    "printers, accessories, and networking equipment\n"
    "- **Check orders** — view your order history and details "
    "(requires verification)\n"
    "- **Place orders** — buy products from our catalog "
    "(requires verification)\n\n"
    "How can I help you today?"
)

SUGGESTIONS_UNAUTH = [
    "Show me all monitors",
    "Search for gaming laptops",
    "What printers do you have?",
    "Tell me about product COM-0001",
]

SUGGESTIONS_AUTH = [
    "Show my recent orders",
    "What's my customer profile?",
    "I want to buy a 24-inch monitor",
    "Search for accessories",
]

DEMO_CUSTOMERS = [
    {"name": "Donald Garcia", "email": "donaldgarcia@example.net", "pin": "7912"},
    {"name": "Michelle James", "email": "michellejames@example.com", "pin": "1520"},
    {"name": "Amanda Spencer", "email": "spenceamanda@example.org", "pin": "2535"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_async_once(coro):
    """Run a single async coroutine synchronously (for one-shot calls)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def stream_chat_events(user_message: str, conv_state: ConversationState):
    """Bridge async chat() generator to sync iterator via thread + queue."""
    q: queue.Queue = queue.Queue()

    def _run():
        loop = asyncio.new_event_loop()
        async def _consume():
            try:
                async for event in chat(user_message, conv_state):
                    q.put(event)
            except Exception as e:
                q.put(e)
            finally:
                q.put(_SENTINEL)
        loop.run_until_complete(_consume())
        loop.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    while True:
        item = q.get()
        if item is _SENTINEL:
            break
        if isinstance(item, Exception):
            raise item
        yield item

    thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Page config (must be first st call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="TechCorp Support",
    page_icon="🖥️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

if "state" not in st.session_state:
    st.session_state.state = ConversationState()

if "display_messages" not in st.session_state:
    st.session_state.display_messages = [
        {"role": "assistant", "content": WELCOME_MESSAGE}
    ]

if "tool_activity" not in st.session_state:
    st.session_state.tool_activity = []

# Fetch MCP tools once on first load
if "mcp_tools" not in st.session_state:
    try:
        tools = run_async_once(get_tools())
        st.session_state.mcp_tools = [
            {
                "name": t.name,
                "description": t.description,
                "params": t.inputSchema.get("properties", {}),
                "required": t.inputSchema.get("required", []),
            }
            for t in tools
        ]
        st.session_state.mcp_connected = True
    except Exception:
        st.session_state.mcp_tools = []
        st.session_state.mcp_connected = False

state: ConversationState = st.session_state.state

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🖥️ TechCorp Support")
    st.divider()

    # --- MCP Server Status ---
    if st.session_state.mcp_connected:
        tool_count = len(st.session_state.mcp_tools)
        st.success(f"MCP Connected · {tool_count} tools")
        with st.expander("View Tools"):
            for tool in st.session_state.mcp_tools:
                st.markdown(f"**`{tool['name']}`**")
                st.caption(tool["description"])
                if tool["params"]:
                    param_parts = []
                    for pname, pinfo in tool["params"].items():
                        req = " *(required)*" if pname in tool["required"] else ""
                        ptype = pinfo.get("type", "any")
                        param_parts.append(f"- `{pname}` ({ptype}){req}")
                    st.markdown("\n".join(param_parts))
                st.markdown("---")
    else:
        st.error("MCP Disconnected")
        st.caption("Could not reach the MCP server. Tool calls will fail.")

    st.divider()

    # --- Authentication Status ---
    if state.is_authenticated:
        st.success(f"Verified: {state.customer_name}")
        st.caption(f"Email: {state.customer_email}")
    else:
        st.info("Not verified — browse products freely or verify with email + PIN.")

    st.divider()

    # --- Demo Credentials ---
    with st.expander("Demo Credentials"):
        st.caption("Try these test accounts to explore authenticated features:")
        for cust in DEMO_CUSTOMERS:
            st.markdown(
                f"**{cust['name']}**  \n"
                f"`{cust['email']}` / PIN `{cust['pin']}`"
            )
        st.caption("_These are demo accounts on the MCP server._")

    # --- Activity Log ---
    with st.expander("Activity Log"):
        if st.session_state.tool_activity:
            for entry in reversed(st.session_state.tool_activity[-20:]):
                icon = "✅" if entry["success"] else "❌"
                st.markdown(
                    f"{icon} **{entry['tool_name']}** — "
                    f"{entry['timestamp']}"
                )
        else:
            st.caption("No tool calls yet.")

    st.divider()

    # --- New Chat + Turn Counter ---
    if st.button("🔄 New Chat", use_container_width=True):
        state.reset()
        st.session_state.display_messages = [
            {"role": "assistant", "content": WELCOME_MESSAGE}
        ]
        st.session_state.tool_activity = []
        st.rerun()

    st.caption(f"Turns: {state.turn_count}")


# ---------------------------------------------------------------------------
# Helper: render suggested questions
# ---------------------------------------------------------------------------

def render_suggestions():
    """Show context-aware suggestion chips. Returns selected text or None."""
    suggestions = SUGGESTIONS_AUTH if state.is_authenticated else SUGGESTIONS_UNAUTH
    cols = st.columns(len(suggestions))
    for col, text in zip(cols, suggestions):
        if col.button(text, use_container_width=True):
            return text
    return None


# ---------------------------------------------------------------------------
# Main Chat Area
# ---------------------------------------------------------------------------

st.title("Customer Support Chat")

# Render chat history
for msg in st.session_state.display_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Suggested questions (shown after last assistant message)
selected_suggestion = render_suggestions()

# Determine user input: either from chat_input or a clicked suggestion
user_input = st.chat_input("Type your message...")
if selected_suggestion:
    user_input = selected_suggestion

if user_input:
    # Show user message
    st.session_state.display_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Stream assistant response
    with st.chat_message("assistant"):
        tool_status = st.empty()
        response_parts: list[str] = []

        try:
            def token_generator():
                for event in stream_chat_events(user_input, state):
                    if isinstance(event, TokenEvent):
                        response_parts.append(event.text)
                        yield event.text
                    elif isinstance(event, ToolCallEvent):
                        display = _TOOL_DISPLAY_NAMES.get(
                            event.tool_name, event.tool_name
                        )
                        tool_status.info(f"⏳ {display}...")
                        st.session_state.tool_activity.append({
                            "tool_name": event.tool_name,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "success": True,  # updated on result
                        })
                    elif isinstance(event, ToolResultEvent):
                        tool_status.empty()
                        # Update the last activity entry with actual status
                        if st.session_state.tool_activity:
                            st.session_state.tool_activity[-1]["success"] = (
                                not event.is_error
                            )

            with st.spinner("Thinking..."):
                st.write_stream(token_generator())
            tool_status.empty()

        except Exception as e:
            tool_status.empty()
            st.error(f"Something went wrong: {e}")
            response_parts = [
                "I'm sorry, I encountered an error. Please try again."
            ]
            st.markdown(response_parts[0])

    st.session_state.display_messages.append(
        {"role": "assistant", "content": "".join(response_parts)}
    )

    # Rerun to update sidebar (auth status may have changed) and suggestions
    st.rerun()
