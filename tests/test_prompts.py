"""Tests for app.agent.prompts."""

from app.agent.prompts import build_system_message, get_guardrail_context, SYSTEM_PROMPT
from app.agent.state import ConversationState


def test_system_prompt_contains_essentials():
    assert "TechCorp" in SYSTEM_PROMPT
    assert "verify" in SYSTEM_PROMPT.lower()
    assert "create_order" in SYSTEM_PROMPT
    assert "list_products" in SYSTEM_PROMPT


def test_guardrail_context_unauth(state):
    ctx = get_guardrail_context(state)
    assert "NOT verified" in ctx
    assert "email" in ctx.lower()
    assert "PIN" in ctx


def test_guardrail_context_auth(auth_state):
    ctx = get_guardrail_context(auth_state)
    assert "VERIFIED" in ctx
    assert auth_state.customer_name in ctx
    assert auth_state.customer_email in ctx
    assert auth_state.customer_id in ctx


def test_build_system_message_unauth(state):
    msg = build_system_message(state)
    assert msg["role"] == "system"
    assert "NOT verified" in msg["content"]
    assert SYSTEM_PROMPT in msg["content"]


def test_build_system_message_auth(auth_state):
    msg = build_system_message(auth_state)
    assert msg["role"] == "system"
    assert "VERIFIED" in msg["content"]
    assert auth_state.customer_name in msg["content"]
