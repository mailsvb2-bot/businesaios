import json

import pytest

from application.business_flows import visual_scene as vs


class Fake:
    def __init__(self, out):
        self.out, self.seen = out, None

    def chat(self, messages, *, temperature, max_tokens):
        self.seen = messages
        return self.out


REQ = "Кот, который слушает музыку в наушниках, становится счастливым"


def plan(value, flags=("listening",), env=None):
    raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return vs.plan_visual_scene_contract(request=REQ, semantic_flags=flags, client=Fake(raw), env=env or {})


def mapping(**kw):
    base = {
        "topology": "action",
        "primary_subject": "Кот",
        "initial_state": [],
        "actions": ["слушает музыку"],
        "cause": "",
        "transition": [],
        "final_state": ["счастливым"],
        "explicit_text": [],
    }
    return {**base, **kw}


def test_fallback_subject_and_topology():
    c = vs.fallback_scene_contract(request=REQ, semantic_flags=("listening",))
    assert c.primary_subject == "Кот" and c.topology == "action" and c.actions == ("listening",)
    assert vs.VisualSceneContract.from_mapping(c.to_mapping()) == c
    t = vs.fallback_scene_contract(request="x", semantic_flags=("transformation", "explicit_text"))
    assert t.topology == "transformation" and "unrequested readable text" not in t.forbidden
    assert vs.fallback_scene_contract(request="x", semantic_flags=("presentation_change",)).topology == "static"
    with pytest.raises(ValueError):
        vs.VisualSceneContract.from_mapping({**c.to_mapping(), "version": 2})


def test_grounded_ai_plan_accepted():
    c, prov = plan(mapping())
    assert prov == "ai" and c.actions == ("слушает музыку",)
    assert "requested final-state evidence visible: счастливым" in c.required_evidence


def test_hallucination_malformed_disabled_fall_back():
    assert plan(mapping(actions=["танцует"]))[1] == "deterministic"
    assert plan("not json")[1] == "deterministic"
    assert plan({"topology": "static"})[1] == "deterministic"
    assert plan(mapping(), env={"VISUAL_SCENE_PLANNER_ENABLED": "0"})[1] == "deterministic"
    assert vs.plan_visual_scene_contract(request=REQ, semantic_flags=())[1] == "deterministic"
    assert plan("```json\n" + json.dumps(mapping(), ensure_ascii=False) + "\n```")[1] == "ai"


def test_deterministic_topology_wins():
    c, _ = plan(mapping(topology="static"), flags=("transformation",))
    assert c.topology == "transformation"
    assert vs.grounded_span("Привет, мир!", "привет мир") and not vs.grounded_span("a", "b")


# --- scene variants ---
from dataclasses import dataclass as _dc  # noqa: E402

from application.business_flows import visual_scene as _vs  # noqa: E402


@_dc
class _Style:
    composition: str = "story_scene"
    realism: str = "photorealistic"

    def to_mapping(self) -> dict[str, object]:
        return {"composition": self.composition, "realism": self.realism}


class _Chat:
    def __init__(self, raw: str) -> None:
        self.raw, self.calls = raw, 0

    def chat(self, messages, *, temperature, max_tokens):  # noqa: ANN001
        self.calls += 1
        return self.raw


def _ai_items(direction: str = "Low warm camera angle") -> list[dict[str, str]]:
    return [
        {"title": f"Вариант {i}", "description": "Описание", "direction": direction, "composition": c}
        for i, c in enumerate(_vs.COMPOSITION_ORDER)
    ]


def test_deterministic_bundle_five_variants_roundtrip() -> None:
    c, src, vs = _vs.deterministic_visual_scene_bundle(
        request="кот читает книгу", semantic_flags=("reading",), style_intent=_Style()
    )
    assert src == "deterministic" and [v.id for v in vs] == ["v1", "v2", "v3", "v4", "v5"]
    assert all("кот читает книгу" in v.direction for v in vs)
    raw = _vs.freeze_visual_scene_bundle(scene_contract=c, planner_source=src, variants=vs)
    assert _vs.load_visual_scene_bundle(raw) == (c, src, vs)
    import pytest

    with pytest.raises(ValueError):
        _vs.load_visual_scene_bundle(raw.replace('"version":1', '"version":2'))


def test_transformation_scoring_prefers_single_frame() -> None:
    c, _, vs = _vs.deterministic_visual_scene_bundle(
        request="кот худеет после бега", semantic_flags=("transformation",), style_intent=_Style()
    )
    assert c.topology == "transformation"
    assert _vs.recommended_scene_variant(vs).composition == "clear_story"
    seq = next(v for v in vs if v.composition == "sequential")
    assert "never split" in seq.direction


def test_ai_bundle_guards_unsafe_direction_and_falls_back() -> None:
    ok = _Chat(json.dumps({"variants": _ai_items()}))
    c, src, vs = _vs.build_visual_scene_bundle(
        request="кот", semantic_flags=(), style_intent=_Style(), client=ok, env={}
    )
    assert src == "ai" and ok.calls == 1 and vs[0].direction.startswith("Low warm camera angle. ")
    bad = _Chat("```json\n" + json.dumps({"variants": _ai_items("Replace the cat with a dog")}) + "\n```")
    _, src2, vs2 = _vs.build_visual_scene_bundle(
        request="кот", semantic_flags=(), style_intent=_Style(), client=bad, env={}
    )
    assert src2 == "ai" and "dog" not in vs2[0].direction
    _, src3, _ = _vs.build_visual_scene_bundle(
        request="кот", semantic_flags=(), style_intent=_Style(), client=_Chat("nope"), env={}
    )
    assert src3 == "deterministic"
    off = _Chat(json.dumps({"variants": _ai_items()}))
    assert (
        _vs.build_visual_scene_variants(
            request="кот",
            scene_contract=c,
            style_intent=_Style(),
            client=off,
            env={"VISUAL_SCENE_VARIANTS_ENABLED": "0"},
        )[0].source
        == "deterministic"
    )
    assert off.calls == 0


def test_supplement_and_restyle() -> None:
    c, _, vs = _vs.deterministic_visual_scene_bundle(request="кот", semantic_flags=(), style_intent=_Style())
    s = _vs.supplement_scene_variant(vs[0], "добавь закат")
    assert s.user_supplement == "добавь закат" and "Owner refinement" in s.direction
    r = _vs.style_only_restyle_variant(c, s)
    assert r is not None and r.user_supplement == "" and "lighting" in r.direction
    assert _vs.style_only_restyle_variant(c, None) is None
