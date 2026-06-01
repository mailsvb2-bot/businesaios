from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

_SPEC = importlib.util.spec_from_file_location(
    "runtime.handlers.ai_ceo_plan_file",
    Path(__file__).resolve().parents[1] / "runtime" / "handlers" / "ai_ceo_plan.py",
)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
handle_ai_ceo_plan = _MOD.handle_ai_ceo_plan


class _Effects:
    def __init__(self):
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return {"ok": True, **kwargs}


class _Planner:
    def build_plan(self, **kwargs):
        return {"steps": [{"kind": "noop"}]}


class _Decision:
    def __init__(self):
        self.decision_id = "d1"
        self.correlation_id = "c1"
        self.issuer_id = "businesaios-core"
        self.action = "ai_ceo_plan@v1"
        self.tenant_id = "t1"


def test_ai_ceo_plan_handler_blocks_without_valid_route():
    effects = _Effects()
    env = SimpleNamespace(decision=SimpleNamespace(decision_id="d1", correlation_id="c1"))
    out = handle_ai_ceo_plan({"user_id": "u1", "tenant_id": "t1"}, effects, env, planner=_Planner())
    assert out["track_event_type"] == "ai_ceo_plan_blocked@v1"


def test_ai_ceo_plan_handler_uses_route_and_planner():
    effects = _Effects()
    env = SimpleNamespace(decision=_Decision())
    out = handle_ai_ceo_plan({"user_id": "u1", "tenant_id": "t1"}, effects, env, planner=_Planner())
    assert out["decision_id"] == "d1"
    assert out["correlation_id"] == "c1"
    assert out["user_id"] == "u1"
    assert out["track_event_type"] == "ai_ceo_plan@v1"
