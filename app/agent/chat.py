"""Core agent loop: LLM <-> MCP tool calls with streaming."""

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.config import settings
from app.mcp_client import call_tool, get_tools
from app.tools import convert_all_tools
from app.agent.state import ConversationState
from app.agent.prompts import build_system_message
from app.agent.guardrails import check_tool_allowed, auto_fix_arguments, process_tool_result, check_loop_limit


# ---------------------------------------------------------------------------
# Event types yielded by chat()
# ---------------------------------------------------------------------------

@dataclass
class ToolCallEvent:
    tool_name: str

@dataclass
class ToolResultEvent:
    tool_name: str
    is_error: bool

@dataclass
class TokenEvent:
    text: str

ChatEvent = ToolCallEvent | ToolResultEvent | TokenEvent


# ---------------------------------------------------------------------------
# OpenAI client + tool cache
# ---------------------------------------------------------------------------

_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
_openai_tools: list[dict] | None = None


async def _get_openai_tools() -> list[dict]:
    """Get OpenAI-formatted tools (cached)."""
    global _openai_tools
    if _openai_tools is None:
        mcp_tools = await get_tools()
        _openai_tools = convert_all_tools(mcp_tools)
    return _openai_tools


# ---------------------------------------------------------------------------
# Message window helper
# ---------------------------------------------------------------------------

def _last_n_turns(messages: list[dict], n: int = 5) -> list[dict]:
    """Return messages covering the last *n* user turns.

    A "turn" starts at each user message.  We walk backwards to find the n-th
    user message and return everything from that point onward.  This keeps
    tool-call / tool-result pairs intact so OpenAI never sees orphaned
    tool_call_ids.  Full history stays in state.messages for guardrail checks.
    """
    if n <= 0:
        return messages

    user_indices: list[int] = [
        i for i, m in enumerate(messages) if m.get("role") == "user"
    ]

    if len(user_indices) <= n:
        return messages  # not enough turns yet — send everything

    cut = user_indices[-n]
    return messages[cut:]


# ---------------------------------------------------------------------------
# Main agent loop
# ---------------------------------------------------------------------------

async def chat(user_message: str, state: ConversationState) -> AsyncGenerator[ChatEvent, None]:
    """Main agent entry point. Yields ChatEvent items (tokens, tool calls, tool results)."""
    state.messages.append({"role": "user", "content": user_message})
    state.turn_count += 1

    openai_tools = await _get_openai_tools()
    tool_call_count = 0

    while True:
        # Send system message + last 5 turns (full history kept in state for guardrails)
        recent = _last_n_turns(state.messages, settings.MAX_HISTORY_TURNS)
        messages = [build_system_message(state)] + recent

        # Stream the OpenAI response
        stream = await _openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            tools=openai_tools,
            tool_choice="auto",
            max_completion_tokens=settings.MAX_COMPLETION_TOKENS,
            stream=True,
        )

        # Accumulate streamed content and tool call deltas
        content_chunks: list[str] = []
        tool_calls_by_index: dict[int, dict] = {}
        finish_reason = None

        async for chunk in stream:
            choice = chunk.choices[0]
            finish_reason = choice.finish_reason or finish_reason
            delta = choice.delta

            # Text token
            if delta.content:
                content_chunks.append(delta.content)
                yield TokenEvent(delta.content)

            # Tool call deltas
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_by_index:
                        tool_calls_by_index[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        tool_calls_by_index[idx]["id"] = tc_delta.id
                    if tc_delta.function and tc_delta.function.name:
                        tool_calls_by_index[idx]["name"] = tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        tool_calls_by_index[idx]["arguments"] += tc_delta.function.arguments

        # --- Finished consuming the stream ---

        if finish_reason == "tool_calls" and tool_calls_by_index:
            # Build assistant message with tool_calls for history
            tc_list = []
            for idx in sorted(tool_calls_by_index):
                tc = tool_calls_by_index[idx]
                tc_list.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                })

            state.messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": tc_list,
            })

            # Execute each tool call
            for tc in tc_list:
                tool_name = tc["function"]["name"]
                try:
                    arguments = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {}

                # Loop guard
                ok, reason = check_loop_limit(tool_call_count, settings.MAX_TOOL_CALLS_PER_TURN)
                if not ok:
                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": reason,
                    })
                    tool_call_count += 1
                    continue

                # Auto-fix: inject customer_id if missing
                arguments = auto_fix_arguments(tool_name, arguments, state)

                # Pre-call guardrail
                allowed, reason = check_tool_allowed(tool_name, arguments, state)
                if not allowed:
                    yield ToolCallEvent(tool_name)
                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": f"Blocked: {reason}",
                    })
                    yield ToolResultEvent(tool_name, True)
                    tool_call_count += 1
                    continue

                # Execute MCP tool
                yield ToolCallEvent(tool_name)
                try:
                    result = await call_tool(tool_name, arguments)
                except Exception as e:
                    result = f"Error calling tool: {e}"

                is_error = result.startswith("Error")

                # Post-call guardrail (may update state)
                result = process_tool_result(tool_name, result, state)

                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
                yield ToolResultEvent(tool_name, is_error)
                tool_call_count += 1

            # Loop back for next LLM call
            continue

        # No tool calls — this is the final text response
        final_text = "".join(content_chunks)
        state.messages.append({"role": "assistant", "content": final_text})
        break


async def chat_sync(user_message: str, state: ConversationState) -> str:
    """Non-streaming version. Returns the full response text."""
    result = ""
    async for event in chat(user_message, state):
        if isinstance(event, TokenEvent):
            result += event.text
    return result
