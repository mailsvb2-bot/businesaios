from __future__ import annotations

from runtime.security.product_action_gate import review_action


def test_gate_denies_disabled_audio() -> None:
    verdict = review_action(product={"modules": {"audio": False}, "domain": "sales", "product_id": "salesbot"}, action="send_audio@v1")
    assert verdict.allow is False
    assert "CAPABILITY_DISABLED:audio" in (verdict.reason or "")


def test_gate_allows_enabled_audio() -> None:
    verdict = review_action(product={"modules": {"audio": True}}, action="send_audio@v1")
    assert verdict.allow is True


def test_gate_allows_unknown_action() -> None:
    verdict = review_action(product={"modules": {}}, action="some_new_action@v1")
    assert verdict.allow is True
