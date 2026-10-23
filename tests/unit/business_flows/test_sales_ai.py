from __future__ import annotations

import json
from functools import partial

import pytest

from application.business_flows import sales_ai as sa
from runtime.handler_impl.domains.business_flow_ops import handle_business_admin, handle_sales_pipeline

NOW = 1_800_000_000_000
GOOD = {
    "intent": "booking",
    "need_is_specific": True,
    "purchase_intent_explicit": True,
    "purchase_readiness": 0.9,
    "confidence": 0.95,
    "explicit_human_request": False,
    "sensitive_context": False,
    "negative_sentiment": False,
    "reply": "Здравствуйте! Подберём удобное время, https://evil.example когда Вам удобно?",
}


def _setup(flow, monkeypatch, answer, provider="yandexgpt"):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    calls = []

    def llm(**kw):
        calls.append(kw)
        return {"ok": True, "text": answer}

    flow.effects.marketing_llm_complete = llm
    flow.run(partial(handle_sales_pipeline, now_ms=NOW), op="add", arg="Анна | сайт")
    return calls


def test_draft_is_note_only_with_redaction_and_conservative_button(flow, monkeypatch) -> None:
    calls = _setup(flow, monkeypatch, "Ответ: " + json.dumps(GOOD, ensure_ascii=False))
    flow.run(handle_business_admin, op="setting", arg="sales_ai = on")
    flow.run(partial(handle_sales_pipeline, now_ms=NOW), op="event", arg="1 contact")
    _, text = flow.run(
        partial(handle_sales_pipeline, now_ms=NOW), op="ai", arg="1 | Хочу записаться, мой тел +7 999 123-45-67, a@b.ru"
    )
    assert "не отправлен клиенту" in text and "evil" not in text and "контакты скрыты" in text
    user = calls[0]["user"]
    assert "999" not in user and "a@b.ru" not in user
    msg = flow.effects.sent[-1]
    cbs = [b["callback_data"] for r in msg["reply_markup"]["inline_keyboard"] for b in r]
    assert cbs[0].endswith(":need")  # one legal step; payment never inferred
    assert msg["track_payload"]["step"] == "lead_note" and msg.get("to_user_id") in (None, "u1")
    assert "🤖 Черновик" in flow.run(partial(handle_sales_pipeline, now_ms=NOW), op="card", arg="1")[1]


def test_refuses_without_consent_or_non_russian_provider_or_no_cloud(flow, monkeypatch) -> None:
    calls = _setup(flow, monkeypatch, json.dumps(GOOD), provider="openai_compat")
    assert "выключен" in flow.run(partial(handle_sales_pipeline, now_ms=NOW), op="ai", arg="1 | привет")[1]
    flow.run(handle_business_admin, op="setting", arg="sales_ai = on")
    assert (
        "YandexGPT или GigaChat" in flow.run(partial(handle_sales_pipeline, now_ms=NOW), op="ai", arg="1 | привет")[1]
    )
    monkeypatch.setenv("LLM_PROVIDER", "gigachat")
    flow.run(handle_business_admin, op="setting", arg="sales_ai_mode = no_cloud")
    assert "запрещена" in flow.run(partial(handle_sales_pipeline, now_ms=NOW), op="ai", arg="1 | привет")[1]
    assert calls == []


def test_malformed_or_low_confidence_answers_fail_closed() -> None:
    with pytest.raises(ValueError):
        sa.parse_analysis("не json")
    with pytest.raises(ValueError):
        sa.parse_analysis(json.dumps({**GOOD, "confidence": 2}))
    with pytest.raises(ValueError):
        sa.parse_analysis(json.dumps({**GOOD, "intent": "pay_now"}))
    low = sa.parse_analysis(json.dumps({**GOOD, "confidence": 0.5}))
    assert sa.milestones(low) == ()
    human = sa.parse_analysis(json.dumps({**GOOD, "explicit_human_request": True}))
    assert sa.milestones(human) == ("handoff",)


def test_verified_offer_only_from_owner_ladder_by_kind_and_readiness() -> None:
    from application.business_flows import ladder as ld

    steps, _ = ld.replay(
        [ld.parse_step("audit | Аудит сайта | 0.95", position=1), ld.parse_step("audit | Экспресс-аудит | 0.5", position=2)]
    )
    a = sa.parse_analysis(json.dumps({**GOOD, "recommended_offer_kind": "audit"}))
    assert sa.verified_offer(steps, a)["title"] == "Экспресс-аудит"
    assert sa.verified_offer(steps, sa.parse_analysis(json.dumps(GOOD))) is None
    bogus = sa.parse_analysis(json.dumps({**GOOD, "recommended_offer_kind": "free_iphone"}))
    assert bogus["recommended_offer_kind"] == "none"
    assert sa.verified_offer(steps, {**a, "recommended_offer_kind": "recurring"}) is None
