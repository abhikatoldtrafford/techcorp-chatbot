"""Shared test fixtures."""

import pytest

from app.agent.state import ConversationState


@pytest.fixture
def state():
    """Fresh unauthenticated conversation state."""
    return ConversationState(session_id="test-session")


@pytest.fixture
def auth_state():
    """Authenticated conversation state."""
    s = ConversationState(session_id="test-session-auth")
    s.is_authenticated = True
    s.customer_id = "41c2903a-f1a5-47b7-a81d-86b50ade220f"
    s.customer_name = "Donald Garcia"
    s.customer_email = "donaldgarcia@example.net"
    return s
