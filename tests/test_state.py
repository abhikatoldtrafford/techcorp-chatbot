"""Tests for app.agent.state."""

from app.agent.state import ConversationState


def test_default_state():
    s = ConversationState()
    assert s.session_id  # auto-generated
    assert s.messages == []
    assert not s.is_authenticated
    assert s.customer_id is None
    assert s.turn_count == 0


def test_state_with_values():
    s = ConversationState(
        session_id="abc",
        is_authenticated=True,
        customer_id="cid-123",
        customer_name="Alice",
        customer_email="alice@example.com",
    )
    assert s.session_id == "abc"
    assert s.is_authenticated
    assert s.customer_name == "Alice"


def test_reset():
    s = ConversationState(session_id="s1")
    s.messages.append({"role": "user", "content": "hi"})
    s.is_authenticated = True
    s.customer_id = "cid"
    s.customer_name = "Bob"
    s.customer_email = "bob@example.com"
    s.turn_count = 5

    s.reset()

    assert s.messages == []
    assert not s.is_authenticated
    assert s.customer_id is None
    assert s.customer_name is None
    assert s.customer_email is None
    assert s.turn_count == 0
    # session_id preserved
    assert s.session_id == "s1"


def test_message_accumulation():
    s = ConversationState()
    s.messages.append({"role": "user", "content": "hello"})
    s.messages.append({"role": "assistant", "content": "hi there"})
    assert len(s.messages) == 2
