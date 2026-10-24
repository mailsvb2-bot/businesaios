from __future__ import annotations

import json
from functools import partial

import pytest

from application.business_flows import event_landing as el
from runtime.handler_impl.domains.business_flow_ops import handle_event_series

NOW = 1_800_000_000_000


def _run(flow, arg, op="landing"):
    return flow.run(partial(handle_event_series, now_ms=NOW), op=op, arg=arg)[1]


def test_template_edit_theme_publish_idempotent(flow) -> None:
    assert "черновик" in _run(flow, "Йога")
    assert "сохранён" in _run(flow, "Йога | about | Утренняя практика")
    assert "Тема" in _run(flow, "Йога | theme | warm")
    text = _run(flow, "Йога")
    assert "Утренняя практика" in text and "тема warm" in text
    assert "опубликован" in _run(flow, "Йога | publish")
    assert "уже опубликована" in _run(flow, "Йога | publish")
    _run(flow, "Йога | for_whom | Новичкам")
    assert "есть новые правки" in _run(flow, "Йога")
    _run(flow, "Йога | reset")
    assert "Утренняя практика" not in _run(flow, "Йога")


def test_ai_russian_only_drafts_without_publishing(flow, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai_compat")
    assert "YandexGPT или GigaChat" in _run(flow, "Йога | ai")
    monkeypatch.setenv("LLM_PROVIDER", "gigachat")
    reply = json.dumps({"about": "Спокойная практика https://x.example", "price": "1"}, ensure_ascii=False)
    flow.effects.marketing_llm_complete = lambda **kw: {"ok": True, "text": reply}
    assert "не опубликован" in _run(flow, "Йога | ai")
    text = _run(flow, "Йога")
    assert "Спокойная практика" in text and "x.example" not in text and "черновик" in text


def test_pure_validation() -> None:
    with pytest.raises(ValueError):
        el.update_section("Йога", "price", "x")
    with pytest.raises(ValueError):
        el.set_theme("Йога", "neon")
    with pytest.raises(ValueError):
        el.parse_ai("not json")
    with pytest.raises(ValueError):
        el.key_for("  ")
