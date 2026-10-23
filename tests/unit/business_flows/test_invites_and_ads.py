from __future__ import annotations

import re
from functools import partial

import pytest

from application.business_flows import ad_proposals as ap
from application.business_flows import invites as iv
from runtime.handler_impl.domains.business_flow_ops import handle_business_admin as H

NOW = 1_800_000_000_000


def test_invite_issue_claim_once_and_stats(flow) -> None:
    _, text = flow.run(partial(H, now_ms=NOW), op="invite_new")
    code = re.search(r"Код: (cpj_\S+)", text).group(1)
    assert code[4:] not in str(flow.store.events)  # only the hash is stored
    _, text = flow.run(partial(H, now_ms=NOW + 1), op="join", arg=code, user_id="cust-1")
    assert "подключены" in text
    _, text = flow.run(partial(H, now_ms=NOW + 2), op="join", arg=code, user_id="cust-2")
    assert "invite_already_used" in text
    _, text = flow.run(partial(H, now_ms=NOW + 3), op="invites")
    assert "Использовано: 1" in text and "Конверсия в подключение: 100%" in text and "Клиентов всего: 1" in text


def test_invite_expiry_and_bad_code() -> None:
    invs = iv.replay([iv.issue("abcdefghijk", now_ms=0)])
    with pytest.raises(ValueError, match="invite_expired"):
        iv.claim(invs, "cpj_abcdefghijk", customer_user_id="u", now_ms=iv.TTL_MS + 1)
    with pytest.raises(ValueError, match="invite_code_invalid"):
        iv.claim(invs, "cpj_wrong", customer_user_id="u", now_ms=1)
    assert iv.stats(invs, now_ms=iv.TTL_MS + 1) == (0, 0)


def test_ad_draft_consent_approve_publish_is_blocked_without_spend(flow) -> None:
    run = partial(flow.run, H)
    run(op="ad_draft", arg="Йога утром | Первое занятие бесплатно | https://example.ru/yoga")
    run(op="ad_draft", arg="Йога утром | Первое занятие бесплатно | https://example.ru/yoga")
    _, text = run(op="ad_list")
    assert text.count("Йога утром") == 1 and "черновик" in text
    _, text = run(op="ad_publish", arg="1")
    assert "согласие" in text
    _, text = run(op="ad_consent", arg="1 | 10 RUB")
    assert "ниже минимума" in text
    run(op="ad_consent", arg="1 | 5000 RUB")
    _, text = run(op="approvals")
    assert "Реклама «Йога утром», кап 5" in text and "ждёт решения" in text
    _, text = run(op="ad_publish", arg="1")
    assert "не одобрено" in text
    run(op="approve", arg="1")
    _, text = run(op="ad_publish", arg="1")
    assert "production_ready=False" in text and "Деньги не тратятся" in text
    run(op="ad_publish", arg="1")
    blocked = [e for e in flow.store.events if (e.get("payload") or {}).get("step") == "ad_publish_blocked"]
    assert len(blocked) == 1
    assert not [s for s in flow.effects.sent if "send_photo" in str(s) or "ads" in str(s.get("effect", ""))]


def test_publish_never_goes_live_when_ready_flag_lies() -> None:
    d = ap.AdDraft("d", "t", "x", "https://a", approval_id="a")
    from application.business_flows.admin import Approval

    with pytest.raises(PermissionError):
        bound = Approval("a", ap.approval_title("t", 0, "RUB"), 0, "RUB", "approved")
        ap.publish_decision(d, {"a": bound}, production_ready=True)


@pytest.mark.parametrize("arg", ["a | b", "a | b | http://x", "x" * 60 + " | b | https://x"])
def test_ad_draft_validation(arg) -> None:
    with pytest.raises(ValueError):
        ap.draft(arg)


def test_ad_unit_economics_with_local_attribution(flow) -> None:
    from runtime.handler_impl.domains.business_flow_ops import handle_sales_pipeline as S

    run = partial(flow.run, H)
    run(op="ad_draft", arg="Йога | Пробное | https://example.ru")
    _, text = run(op="ad_report")
    assert "Нет данных" in text
    _, text = run(op="ad_stats", arg="1 | 10 | 20 | 100 RUB")
    assert "кликов больше" in text
    run(op="ad_stats", arg="1 | 1000 | 50 | 2000 RUB")
    for name in ("Анна", "Борис"):
        flow.run(S, op="add", arg=f"{name} | ad1")
    flow.run(S, op="add", arg="Вера | сайт")
    flow.run(S, op="event", arg="1 paid")
    _, text = run(op="ad_report")
    assert "CTR 5.00%" in text and "CPC 40,00" in text.replace(".", ",")
    assert "лиды 2" in text and "клиенты 1" in text and "CAC 2" in text


def test_publish_decision_requires_approval_bound_to_exact_draft_and_cap() -> None:
    from application.business_flows import ad_proposals as apz
    from application.business_flows import admin as adm

    d = apz.AdDraft("d1", "Йога", "t", "https://x", "awaiting_approval", "a1", 500_000, "RUB")
    good = adm.Approval("a1", apz.approval_title("Йога", 500_000, "RUB"), 500_000, "RUB")
    good.status = "approved"
    text, fact = apz.publish_decision(d, {"a1": good}, production_ready=False)
    assert fact and fact["step"] == "ad_publish_blocked"
    wrong = adm.Approval("a1", good.title, 100_000, "RUB")
    wrong.status = "approved"
    text, fact = apz.publish_decision(d, {"a1": wrong}, production_ready=False)
    assert fact is None and "другое действие" in text
