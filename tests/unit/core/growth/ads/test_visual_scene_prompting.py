from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.growth.ads.creative.pipeline import visual_scene_breakdown
from core.growth.ads.creative.prompting import parse_scene_json, scene_from_text, scene_key_elements
from core.llm.agent import LLMTaskContext
from runtime._internal.effects_domains.visual_creative_gateway import visual_direction_prompt


def test_scene_json_strict_and_rule_fallback() -> None:
    assert parse_scene_json('{"subject":"диван","action":"чистят диван"}') == {
        "subject": "диван", "action": "чистят диван",
    }
    assert parse_scene_json('{"subject":"диван","untrusted":true}') is None
    assert parse_scene_json('{"before":"старый диван","after":"новый диван"}') is None
    assert scene_from_text("Химчистка диванов")["subject"] == "Химчистка диванов"
    assert scene_key_elements({"subject": "диван", "action": "мастер чистит диван"}) == ["мастер чистит диван"]


def test_art_director_calls_canonical_llm_task_and_falls_back() -> None:
    ctx = LLMTaskContext(tenant_id="tenant-1", offer={"request": "Чистка дивана"})
    calls = []

    class Agent:
        def run_task(self, task, context):
            calls.append((task.value, context.tenant_id))
            return SimpleNamespace(json={"subject": "диван", "action": "мастер чистит диван"}, text="")

    result = visual_scene_breakdown(Agent(), ctx, "Чистка дивана")
    assert result["action"] == "мастер чистит диван"
    assert calls == [("ads.visual.scene", "tenant-1")]
    assert visual_scene_breakdown(None, ctx, "Чистка дивана")["subject"]


def test_russian_image_prompt_keeps_action_first_and_blocks_invented_discount() -> None:
    scene = {"subject": "диван", "action": "мастер чистит диван", "style": "скидка 35%",
             "before": "диван в пятнах", "after": "чистый диван", "process": "чистка щеткой"}
    prompt = visual_direction_prompt(scene, owner_context="диван мастер чистит диван")
    assert len(prompt) <= 500
    assert prompt.startswith("Триптих")
    assert "скидка" not in prompt
    assert "35%" not in prompt
    with pytest.raises(ValueError, match="visual_direction_invalid"):
        visual_direction_prompt({"subject": "диван", "discount": "50%"}, owner_context="диван")
