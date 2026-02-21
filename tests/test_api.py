"""Tests for app.api — FastAPI endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.agent.chat import TokenEvent


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint_ok(client):
    mock_tool = MagicMock()
    mock_tool.name = "list_products"

    with patch("app.api.routes.get_tools", new_callable=AsyncMock, return_value=[mock_tool]):
        response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mcp_connected"] is True
    assert data["model"] == "gpt-5-mini"


def test_health_endpoint_degraded(client):
    with patch("app.api.routes.get_tools", new_callable=AsyncMock, side_effect=Exception("fail")):
        response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["mcp_connected"] is False


def test_chat_endpoint_returns_sse(client):
    async def mock_chat(msg, state):
        yield TokenEvent("Hello from bot!")

    with patch("app.api.routes.chat", side_effect=mock_chat):
        response = client.post(
            "/chat",
            json={"session_id": "test", "message": "Hi"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "Hello from bot!" in response.text
