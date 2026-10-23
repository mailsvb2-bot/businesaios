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


def test_scopes_quiet_hours_and_authorization_binding() -> None:
    import pytest

    from application.business_flows import admin as ad
    from application.business_flows import automation_policy as ap

    pols = ap.replay([ap.draft([], "allow=followup,growth | days=30", now_ms=0)])
    pols = ap.replay([ap.draft([], "allow=followup,growth | days=30", now_ms=0), ap.approve(pols, now_ms=0)])
    noon_msk, night_msk = 9 * 3600_000, 20 * 3600_000  # 12:00 / 23:00 MSK on day 0
    assert ap.check(pols, "followup", channel="telegram", now_ms=noon_msk)[0] == "allow"
    v, why = ap.check(pols, "followup", channel="telegram", now_ms=night_msk)
    assert v == "deny" and "тихие часы" in why[0]
    assert (
        ap.check(pols, "followup", channel="telegram", now_ms=night_msk, timezone_name="America/New_York")[0] == "allow"
    )
    assert ap.check(pols, "growth", channel="sms", now_ms=noon_msk)[0] == "deny"
    approvals = {"a1": ad.Approval("a1", "Автоматизация: ads (vk)", 5000, "RUB", status="approved")}
    ap.authorize(approvals, "a1", title="Автоматизация: ads (vk)", amount_minor=5000)
    with pytest.raises(PermissionError):
        ap.authorize(approvals, "a1", title="Автоматизация: ads (vk)", amount_minor=9000)
    with pytest.raises(PermissionError):
        ap.authorize(approvals, "zz", title="x", amount_minor=0)
