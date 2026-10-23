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
    base = {"topology": "action", "primary_subject": "Кот", "initial_state": [], "actions": ["слушает музыку"],
            "cause": "", "transition": [], "final_state": ["счастливым"], "explicit_text": []}
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
