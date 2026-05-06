from __future__ import annotations

from canon.decision_gateway_rules import assert_decision_gateway_api


def test_decision_gateway_api_rejects_decision_like_methods() -> None:
    try:
        assert_decision_gateway_api(("route", "select_winner"))
    except RuntimeError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
