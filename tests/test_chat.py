"""Tests for app.agent.chat — full agent loop with mocked OpenAI + MCP."""

from unittest.mock import AsyncMock, MagicMock, patch
import json

import pytest

from app.agent.chat import chat, chat_sync, TokenEvent, ToolCallEvent, ToolResultEvent
from app.agent.state import ConversationState


# ---------------------------------------------------------------------------
# Streaming mock helpers
# ---------------------------------------------------------------------------

class MockAsyncStream:
    """Mock for an OpenAI async streaming response."""

    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        return self._iter_chunks()

    async def _iter_chunks(self):
        for chunk in self._chunks:
            yield chunk


def _make_chunk(content=None, tool_calls=None, finish_reason=None):
    """Create a single streaming chunk."""
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = tool_calls

    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = finish_reason

    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def _make_tool_call_delta(index, tc_id=None, name=None, arguments=None):
    """Create a tool call delta object for streaming."""
    tc = MagicMock()
    tc.index = index
    tc.id = tc_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


def _mock_streaming_text_response(text):
    """Create a streaming response that delivers text in multiple chunks."""
    words = text.split(" ")
    chunks = []
    for i, word in enumerate(words):
        token = word if i == 0 else " " + word
        is_last = i == len(words) - 1
        chunks.append(_make_chunk(
            content=token,
            finish_reason="stop" if is_last else None,
        ))
    return MockAsyncStream(chunks)


def _mock_streaming_tool_response(tool_calls_data):
    """Create a streaming response with tool calls.

    tool_calls_data: list of (id, name, arguments_dict)
    """
    chunks = []
    for idx, (tc_id, name, args) in enumerate(tool_calls_data):
        args_str = json.dumps(args)
        # First chunk: id + name
        chunks.append(_make_chunk(
            tool_calls=[_make_tool_call_delta(idx, tc_id=tc_id, name=name, arguments=None)],
        ))
        # Second chunk: arguments
        chunks.append(_make_chunk(
            tool_calls=[_make_tool_call_delta(idx, arguments=args_str)],
        ))
    # Final chunk with finish_reason
    chunks.append(_make_chunk(finish_reason="tool_calls"))
    return MockAsyncStream(chunks)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_openai():
    with patch("app.agent.chat._openai_client") as mock:
        mock.chat.completions.create = AsyncMock()
        yield mock


@pytest.fixture
def mock_mcp():
    with patch("app.agent.chat.call_tool", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_tools():
    """Mock get_tools and _openai_tools cache."""
    mock_tool = MagicMock()
    mock_tool.name = "search_products"
    mock_tool.description = "Search"
    mock_tool.inputSchema = {"type": "object", "properties": {"query": {"type": "string"}}}

    with patch("app.agent.chat.get_tools", new_callable=AsyncMock, return_value=[mock_tool]):
        with patch("app.agent.chat._openai_tools", [
            {"type": "function", "function": {"name": "search_products", "description": "Search", "parameters": {}}}
        ]):
            yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simple_text_response(mock_openai, mock_mcp, mock_tools):
    """User sends a greeting, LLM responds with text (no tools)."""
    mock_openai.chat.completions.create.return_value = _mock_streaming_text_response(
        "Hello! How can I help you today?"
    )

    state = ConversationState(session_id="test")
    result = await chat_sync("Hi!", state)

    assert result == "Hello! How can I help you today?"
    assert len(state.messages) == 2  # user + assistant


@pytest.mark.asyncio
async def test_tool_call_flow(mock_openai, mock_mcp, mock_tools):
    """LLM calls a tool, gets result, then responds with text."""
    mock_openai.chat.completions.create.side_effect = [
        _mock_streaming_tool_response([("call_1", "search_products", {"query": "monitor"})]),
        _mock_streaming_text_response("We have 40 monitors available!"),
    ]
    mock_mcp.return_value = "Found 40 products matching 'monitor'"

    state = ConversationState(session_id="test")
    result = await chat_sync("What monitors do you have?", state)

    assert "40 monitors" in result
    mock_mcp.assert_called_once_with("search_products", {"query": "monitor"})


@pytest.mark.asyncio
async def test_auth_tool_blocked_when_unauth(mock_openai, mock_mcp, mock_tools):
    """Auth-required tool is blocked when customer is not verified."""
    mock_openai.chat.completions.create.side_effect = [
        _mock_streaming_tool_response([("call_1", "list_orders", {"customer_id": "some-id"})]),
        _mock_streaming_text_response("Please verify first with email and PIN."),
    ]

    state = ConversationState(session_id="test")
    result = await chat_sync("Show my orders", state)

    # MCP tool should NOT have been called
    mock_mcp.assert_not_called()
    assert "verify" in result.lower() or "Please" in result


@pytest.mark.asyncio
async def test_verify_pin_updates_state(mock_openai, mock_mcp, mock_tools):
    """verify_customer_pin success updates conversation state."""
    verify_result = (
        "✓ Customer verified: Donald Garcia\n"
        "Customer ID: 41c2903a-f1a5-47b7-a81d-86b50ade220f\n"
        "Email: donaldgarcia@example.net\n"
        "Role: admin"
    )
    mock_openai.chat.completions.create.side_effect = [
        _mock_streaming_tool_response([
            ("call_1", "verify_customer_pin", {"email": "donaldgarcia@example.net", "pin": "7912"})
        ]),
        _mock_streaming_text_response("Welcome, Donald!"),
    ]
    mock_mcp.return_value = verify_result

    state = ConversationState(session_id="test")
    await chat_sync("My email is donaldgarcia@example.net, PIN 7912", state)

    assert state.is_authenticated
    assert state.customer_name == "Donald Garcia"
    assert state.customer_id == "41c2903a-f1a5-47b7-a81d-86b50ade220f"


@pytest.mark.asyncio
async def test_streaming_yields_multiple_chunks(mock_openai, mock_mcp, mock_tools):
    """chat() yields more than one TokenEvent for a multi-word response."""
    mock_openai.chat.completions.create.return_value = _mock_streaming_text_response(
        "Here are some great monitors for you!"
    )

    state = ConversationState(session_id="test")
    token_events = []
    async for event in chat("Show monitors", state):
        if isinstance(event, TokenEvent):
            token_events.append(event)

    assert len(token_events) > 1, "Should stream multiple token chunks"
    full_text = "".join(e.text for e in token_events)
    assert full_text == "Here are some great monitors for you!"


@pytest.mark.asyncio
async def test_tool_events_emitted(mock_openai, mock_mcp, mock_tools):
    """chat() emits ToolCallEvent and ToolResultEvent around tool execution."""
    mock_openai.chat.completions.create.side_effect = [
        _mock_streaming_tool_response([("call_1", "search_products", {"query": "laptop"})]),
        _mock_streaming_text_response("Found laptops!"),
    ]
    mock_mcp.return_value = "3 laptops found"

    state = ConversationState(session_id="test")
    events = []
    async for event in chat("Find laptops", state):
        events.append(event)

    tool_call_events = [e for e in events if isinstance(e, ToolCallEvent)]
    tool_result_events = [e for e in events if isinstance(e, ToolResultEvent)]

    assert len(tool_call_events) == 1
    assert tool_call_events[0].tool_name == "search_products"
    assert len(tool_result_events) == 1
    assert tool_result_events[0].tool_name == "search_products"
    assert tool_result_events[0].is_error is False
