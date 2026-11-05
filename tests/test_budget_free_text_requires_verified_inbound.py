"""Negative regressions: unverified single-recipient text must consume budgets."""

import pytest

from core.safety.controls.action_budget.models import is_budget_free_text_message


@pytest.mark.parametrize("payload", [
    {"tenant_id": "tenant-a", "user_id": "recipient-a", "text": "hello"},
    {"tenant_id": "tenant-a", "user_id": "recipient-a", "text": "hello",
     "channel": "telegram", "chat_id": "recipient-a", "estimated_cost": 0},
    {"tenant_id": "tenant-a", "user_id": "recipient-a", "text": "hello",
     "channel": "vk", "chat_id": "recipient-a", "recipient_count": 1},
    {"tenant_id": "tenant-a", "user_id": "recipient-a", "text": "hello",
     "channel": "max", "chat_id": "recipient-a",
     "meta": {"inbound_user_reply": {"tenant_id": "tenant-a", "channel": "max"}}},
])
def test_unverified_single_text_cannot_bypass_budget(payload):
    assert not is_budget_free_text_message("send_message@v1", payload)


def test_other_action_never_budget_free():
    assert not is_budget_free_text_message("charge@v1", {
        "tenant_id": "tenant-a", "user_id": "recipient-a", "text": "hello"
    })
