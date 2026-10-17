"""Archived Phase-18 regressions, retained against canonical main without donor code."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.growth.ads.creative.pipeline import visual_scene_breakdown
from core.growth.ads.creative.prompting import parse_scene_json, scene_from_text, scene_key_elements
from runtime._internal.effects_domains.visual_creative_gateway import visual_direction_prompt


@pytest.mark.parametrize(("text", "before", "after", "process"), [
    ("Старый диван превращается из потёртого в как новый после химчистки", "потёртого", "как новый", "химчистки"),
    ("Сад: был заросший, стал ухоженным благодаря садовнику", "заросший", "ухоженным", "садовнику"),
    ("Волосы меняются от тусклых до блестящих", "тусклых", "блестящих", ""),
])
def test_change_recognition_across_domains(text, before, after, process):
    scene = scene_from_text(text)
    assert (scene["before"], scene["after"], scene.get("process", "")) == (before, after, process)


@pytest.mark.parametrize("text", ["Бариста наливает латте в уютной кофейне", "Ёж в наушниках из Москвы", "Йога на рассвете"])
def test_non_transformation_is_not_a_diptych(text):
    scene = scene_from_text(text)
    assert set(scene) == {"subject"}
    assert "Диптих" not in visual_direction_prompt(scene, owner_context=text)


def test_strict_scene_json_contract():
    assert parse_scene_json('{"subject": "мастер", "action": "чинит часы"}') == {
        "subject": "мастер", "action": "чинит часы"
    }
    for raw in ('{"subject": ""}', '{"subject": "кот", "price": "1"}',
                '{"subject": "кот", "before": "мокрый"}', "не json", '["x"]', {"subject": 1}):
        assert parse_scene_json(raw) is None


def test_prompt_panels_and_length(monkeypatch):
    scene = {"subject": "кухня", "action": "мастер красит стены", "before": "облупленные стены",
             "process": "покраска", "after": "свежие светлые стены", "light": "дневной свет " * 20}
    prompt = visual_direction_prompt(scene, owner_context="кухня")
    assert prompt.startswith("Триптих")
    assert len(prompt) <= 500
    assert visual_direction_prompt({k: v for k, v in scene.items() if k != "process"}, owner_context="").startswith("Диптих")
    monkeypatch.setenv("VISUAL_TRANSFORMATION_DIPTYCH", "0")
    assert visual_direction_prompt(scene, owner_context="").startswith("Мастер красит стены")


def test_unverified_marketing_facts_are_removed():
    prompt = visual_direction_prompt({"subject": "кроссовки", "style": "Nike", "palette": "-50%"}, owner_context="кроссовки")
    assert "Nike" not in prompt and "50" not in prompt
    assert "Nike" in visual_direction_prompt({"subject": "кроссовки", "style": "Nike"}, owner_context="кроссовки Nike")
    assert scene_key_elements({"subject": "сад", "after": "ухоженный"}) == ["сад", "ухоженный"]


def test_art_director_uses_canonical_llm_task_and_falls_back():
    llm = Mock()
    llm.run_task.return_value = SimpleNamespace(json={"subject": "пёс", "action": "ловит мяч"}, text="")
    assert visual_scene_breakdown(llm, Mock(), "пёс") == {"subject": "пёс", "action": "ловит мяч"}
    assert llm.run_task.call_args.args[0].value == "ads.visual.scene"
    llm.run_task.side_effect = RuntimeError("down")
    assert visual_scene_breakdown(llm, Mock(), "Комната стала из тёмной в светлую")["after"] == "светлую"


def test_scene_changes_approval_fingerprint():
    from application.visual_creative_semantics.phase18_advertising_studio import prepare_advertising_creatives
    kwargs = dict(tenant_id="t", business_id="b", campaign_id="c", headline="Химчистка",
                  description="Чистим диваны", brand_context="бренд", campaign_goal="заявки",
                  kind="image", formats=("square",))
    rule = prepare_advertising_creatives(**kwargs)
    llm = prepare_advertising_creatives(**kwargs, scene={"subject": "диван", "action": "мастер чистит диван"})
    assert dict(llm[0].visual_direction)["action"] == "мастер чистит диван"
    assert rule[0].approval_fingerprint != llm[0].approval_fingerprint


def _marketing_effects(monkeypatch, gateway):
    from runtime._internal.effects_domains import marketing
    monkeypatch.setattr(marketing, "visual_gateway_json", gateway)
    monkeypatch.setattr(marketing, "assert_called_from_executor", lambda: None)
    effects = marketing.MarketingEffectsMixin()
    effects.http_transport, effects.event_log = None, Mock()
    monkeypatch.setattr(effects, "_visual_tenant", lambda tenant_id, op: tenant_id, raising=False)
    return effects


@pytest.mark.parametrize(("qa", "should_retry"), [
    ({"status": "needs_review", "issues": ["не видно: собака ловит мяч"], "summary": ""}, True),
    ({"status": "pass", "issues": [], "summary": ""}, False),
    (RuntimeError("gateway unavailable"), False),
])
def test_semantic_qa_is_bounded_and_fails_safe(monkeypatch, qa, should_retry):
    calls = []
    def gateway(method, path, payload, *, timeout_s=30, transport=None):
        calls.append((path, payload))
        if path.endswith("semantic-qa"):
            if isinstance(qa, Exception):
                raise qa
            return qa
        return {"id": f"j{len(calls)}", "provider": "yandexart", "scope_id": "t",
                "kind": "image", "status": "succeeded", "asset_ready": True}
    result = _marketing_effects(monkeypatch, gateway).generate_visual_creative(
        decision_id="d", correlation_id="c", tenant_id="t", user_id="u", kind="image",
        prompt="собака в парке", visual_direction={"subject": "собака", "action": "собака ловит мяч", "setting": "парк"})
    qa_calls = [p for url, p in calls if url.endswith("semantic-qa")]
    generations = [p for url, p in calls if url.endswith("generations")]
    assert len(qa_calls) == 1
    assert len(generations) == (2 if should_retry else 1)
    if should_retry:
        assert generations[1]["idempotency_key"].endswith(":q1")
        assert "Обязательно видно" in generations[1]["prompt"]
    assert result is not None


def test_semantic_qa_can_be_disabled_without_network_call(monkeypatch):
    monkeypatch.setenv("VISUAL_SEMANTIC_RETRY", "0")
    paths = []
    def gateway(method, path, payload, *, timeout_s=30, transport=None):
        paths.append(path)
        return {"id": "j", "provider": "yandexart", "scope_id": "t",
                "kind": "image", "status": "succeeded", "asset_ready": True}
    _marketing_effects(monkeypatch, gateway).generate_visual_creative(
        decision_id="d", correlation_id="c", tenant_id="t", user_id="u", kind="image",
        prompt="кот", visual_direction={"subject": "кот"})
    assert paths == ["/v1/creative/generations"]
