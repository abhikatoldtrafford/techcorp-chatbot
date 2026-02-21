from uuid import uuid4

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    message: str


class ChatChunk(BaseModel):
    token: str | None = None
    done: bool = False


class HealthResponse(BaseModel):
    status: str
    mcp_connected: bool
    model: str
