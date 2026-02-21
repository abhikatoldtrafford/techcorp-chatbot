"""Tests for app.agent.guardrails."""

import pytest

from app.agent.guardrails import (
    check_tool_allowed,
    process_tool_result,
    check_loop_limit,
)
from app.agent.state import ConversationState


# ---------------------------------------------------------------------------
# Pre-call guard
# ---------------------------------------------------------------------------

class TestCheckToolAllowed:
    def test_public_tool_always_allowed(self, state):
        ok, _ = check_tool_allowed("list_products", {}, state)
        assert ok

    def test_auth_tool_blocked_when_unauth(self, state):
        ok, reason = check_tool_allowed("list_orders", {}, state)
        assert not ok
        assert "not verified" in reason.lower()

    def test_auth_tool_allowed_when_auth(self, auth_state):
        ok, _ = check_tool_allowed(
            "list_orders",
            {"customer_id": auth_state.customer_id},
            auth_state,
        )
        assert ok

    def test_wrong_customer_id_blocked(self, auth_state):
        ok, reason = check_tool_allowed(
            "get_customer",
            {"customer_id": "wrong-id"},
            auth_state,
        )
        assert not ok
        assert "currently verified" in reason.lower()

    def test_create_order_blocked_without_confirmation(self, auth_state):
        auth_state.messages = [
            {"role": "user", "content": "I want to buy a monitor"},
        ]
        ok, reason = check_tool_allowed(
            "create_order",
            {"customer_id": auth_state.customer_id, "items": []},
            auth_state,
        )
        assert not ok
        assert "confirmation" in reason.lower()

    def test_create_order_allowed_with_confirmation(self, auth_state):
        auth_state.messages = [
            {"role": "assistant", "content": "Order summary: 1x Monitor $166.85. Confirm?"},
            {"role": "user", "content": "Yes, go ahead"},
        ]
        ok, _ = check_tool_allowed(
            "create_order",
            {"customer_id": auth_state.customer_id, "items": []},
            auth_state,
        )
        assert ok

    def test_verify_pin_always_allowed(self, state):
        ok, _ = check_tool_allowed(
            "verify_customer_pin",
            {"email": "test@example.com", "pin": "1234"},
            state,
        )
        assert ok

    def test_list_orders_blocked_without_customer_id(self, auth_state):
        ok, reason = check_tool_allowed("list_orders", {}, auth_state)
        assert not ok
        assert "missing customer_id" in reason.lower()

    def test_get_customer_blocked_without_customer_id(self, auth_state):
        ok, reason = check_tool_allowed("get_customer", {}, auth_state)
        assert not ok
        assert "missing customer_id" in reason.lower()


# ---------------------------------------------------------------------------
# Post-call guard
# ---------------------------------------------------------------------------

class TestProcessToolResult:
    def test_verify_pin_updates_state(self, state):
        result = (
            "✓ Customer verified: Donald Garcia\n"
            "Customer ID: 41c2903a-f1a5-47b7-a81d-86b50ade220f\n"
            "Email: donaldgarcia@example.net\n"
            "Role: admin"
        )
        process_tool_result("verify_customer_pin", result, state)

        assert state.is_authenticated
        assert state.customer_id == "41c2903a-f1a5-47b7-a81d-86b50ade220f"
        assert state.customer_name == "Donald Garcia"
        assert state.customer_email == "donaldgarcia@example.net"

    def test_verify_pin_error_no_state_change(self, state):
        result = "Error: Customer not found or PIN incorrect"
        process_tool_result("verify_customer_pin", result, state)

        assert not state.is_authenticated
        assert state.customer_id is None

    def test_truncates_long_results(self, state):
        long_result = "Line\n" * 2000  # way over 4000 chars
        result = process_tool_result("list_products", long_result, state)
        assert len(result) < len(long_result)
        assert "truncated" in result

    def test_short_results_unchanged(self, state):
        result = process_tool_result("get_product", "Product: Monitor", state)
        assert result == "Product: Monitor"


# ---------------------------------------------------------------------------
# Loop guard
# ---------------------------------------------------------------------------

class TestLoopGuard:
    def test_under_limit(self):
        ok, _ = check_loop_limit(3, 5)
        assert ok

    def test_at_limit(self):
        ok, reason = check_loop_limit(5, 5)
        assert not ok
        assert "limit" in reason.lower()

    def test_over_limit(self):
        ok, _ = check_loop_limit(10, 5)
        assert not ok
