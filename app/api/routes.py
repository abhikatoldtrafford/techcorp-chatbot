import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.models import ChatRequest, HealthResponse
from app.agent.state import ConversationState
from app.agent.chat import chat, TokenEvent, ToolCallEvent, ToolResultEvent
from app.mcp_client import get_tools
from app.config import settings

router = APIRouter()

# In-memory session store
_sessions: dict[str, ConversationState] = {}


def _get_state(session_id: str) -> ConversationState:
    if session_id not in _sessions:
        _sessions[session_id] = ConversationState(session_id=session_id)
    return _sessions[session_id]


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """Chat endpoint with Server-Sent Events streaming."""
    state = _get_state(req.session_id)

    async def event_stream():
        async for event in chat(req.message, state):
            if isinstance(event, TokenEvent):
                data = json.dumps({"token": event.text})
            elif isinstance(event, ToolCallEvent):
                data = json.dumps({"tool_call": event.tool_name})
            elif isinstance(event, ToolResultEvent):
                data = json.dumps({"tool_result": event.tool_name, "is_error": event.is_error})
            else:
                continue
            yield f"data: {data}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/health", response_model=HealthResponse)
async def health():
    """Health check — verifies MCP server connectivity."""
    try:
        tools = await get_tools()
        mcp_ok = len(tools) > 0
    except Exception:
        mcp_ok = False

    return HealthResponse(
        status="ok" if mcp_ok else "degraded",
        mcp_connected=mcp_ok,
        model=settings.OPENAI_MODEL,
    )
