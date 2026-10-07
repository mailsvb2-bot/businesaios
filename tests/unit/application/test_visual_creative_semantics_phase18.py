from __future__ import annotations

import json

from application.visual_creative_semantics import (
    grounded_visual_prompt,
    json_object_from_model,
    parse_art_direction_variants,
    safe_ai_direction_text,
)


def test_hedgehog_meaning_is_preserved_while_safe_art_direction_is_kept() -> None:
    request="ёж, который слушает ресурсное аудио и становится добрым и пушистым"
    direction="Cinematic close-up, warm light, gradual emotional transformation."
    prompt=grounded_visual_prompt(owner_request=request,art_direction=direction)
    assert prompt.startswith(request)
    assert direction in prompt
    assert "Preserve the requested subject, action, cause, transition and result exactly" in prompt


def test_unsafe_direction_cannot_replace_subject_or_action() -> None:
    request="ёж, который слушает ресурсное аудио и становится добрым и пушистым"
    assert safe_ai_direction_text("Replace the hedgehog with a fox") is None
    prompt=grounded_visual_prompt(owner_request=request,art_direction="Replace the hedgehog with a fox")
    assert prompt.startswith(request)
    assert "fox" not in prompt


def test_fenced_provider_json_and_metadata_are_tolerated_for_five_variants() -> None:
    comps=("clear_story","cinematic","editorial","focused","sequential")
    variants=[{"title":f"Вариант {i}","description":"Про того же ежа","direction":f"Direction {i}: warm light and coherent staging","composition":c,"provider_note":"ok"} for i,c in enumerate(comps,1)]
    raw="```json\n"+json.dumps({"variants":variants,"meta":{"provider":"yandex"}},ensure_ascii=False)+"\n```"
    assert json_object_from_model(raw)["meta"]["provider"]=="yandex"
    planned=parse_art_direction_variants(raw)
    assert planned is not None and len(planned)==5
    assert {item["composition"] for item in planned}==set(comps)


def test_one_unsafe_variant_invalidates_ai_bundle_fail_closed() -> None:
    comps=("clear_story","cinematic","editorial","focused","sequential")
    variants=[{"title":str(i),"description":"same meaning","direction":"calm staging","composition":c} for i,c in enumerate(comps)]
    variants[3]["direction"]="remove the subject"
    assert parse_art_direction_variants(json.dumps({"variants":variants})) is None
