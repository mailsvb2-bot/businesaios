from __future__ import annotations

from functools import partial

from application.business_flows import automation_policy as ap
from runtime.handler_impl.domains.business_flow_ops import handle_business_admin as H

NOW = 1_800_000_000_000


def test_no_policy_denies_everything() -> None:
    assert ap.check([], "post", now_ms=NOW)[0] == "deny"


def test_lifecycle_and_check_via_handler(flow) -> None:
    run = lambda op, arg="", t=NOW: flow.run(partial(H, now_ms=t), op=op, arg=arg)[1]  # noqa: E731
    assert "нет" in run("policy").casefold()
    assert "v1" in run(
        "policy_draft", "allow=post,ads | deny=refund | channels=telegram | max=ads:5000 RUB | approve=ads | days=10"
    )
    assert "⛔" in run("policy_check", "post | telegram")
    run("policy_approve")
    assert "✅ Разрешено" in run("policy_check", "post | telegram")
    assert "канал vk" in run("policy_check", "post | vk")
    assert "⛔" in run("policy_check", "refund | telegram | 1 RUB")
    assert "выше лимита" in run("policy_check", "ads | telegram | 6000 RUB")
    assert "🧾" in run("policy_check", "ads | telegram | 1000 RUB")
    run("policy_check", "ads | telegram | 1000 RUB")
    assert run("approvals").count("Автоматизация: ads") == 1
    assert "⛔ Запрещено" in run("policy_check", "post | telegram", NOW + 11 * ap.DAY_MS)  # expired
    run("policy_draft", "allow=post | days=30")
    run("policy_approve")
    assert "v2 (approved)" in run("policy") and "⛔" in run("policy_check", "ads | telegram | 1 RUB")
    run("policy_revoke")
    assert "всё запрещено" in run("policy")


def test_parse_rejects_conflicts() -> None:
    import pytest

    with pytest.raises(ValueError):
        ap.parse_spec("allow=post | deny=post")
    with pytest.raises(ValueError):
        ap.parse_spec("deny=post")
