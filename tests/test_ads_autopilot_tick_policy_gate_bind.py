from __future__ import annotations

import importlib.util
from pathlib import Path

from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _load_handler():
    path = Path(__file__).resolve().parents[1] / "runtime" / "handlers" / "ads_autopilot_tick.py"
    spec = importlib.util.spec_from_file_location("ads_autopilot_tick_module", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.handle_ads_autopilot_tick


class _Effects:
    def __init__(self) -> None:
        self.messages = []

    def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return kwargs


class _Engine:
    def tick(self, req):
        return type("R", (), {"status": "ok", "stop_loss": {"allowed": True, "reason": "ok"}, "plan": {"commands": []}, "applied": {"status": "skipped"}})()


class _Decision:
    def __init__(self, decision_id: str, correlation_id: str):
        self.decision_id = decision_id
        self.correlation_id = correlation_id
        self.issuer_id = "businesaios-core"
        self.action = "ads_autopilot_tick@v1"


class _Env:
    def __init__(self, decision_id: str, correlation_id: str):
        self.decision = _Decision(decision_id, correlation_id)


def test_ads_autopilot_tick_uses_event_sourced_policy_gate_cooldown() -> None:
    handle_ads_autopilot_tick = _load_handler()
    es = MemoryEventStore()
    fx = _Effects()
    payload = {"tenant_id": "t1", "decision_id": "d1", "correlation_id": "c1", "user_id": "u1", "chat_id": "ch1", "dry_run": True}
    handle_ads_autopilot_tick(payload, fx, env=_Env("d1", "c1"), engine=_Engine(), event_store=es)

    fx2 = _Effects()
    payload2 = {"tenant_id": "t1", "decision_id": "d2", "correlation_id": "c2", "user_id": "u1", "chat_id": "ch1", "dry_run": True}
    handle_ads_autopilot_tick(payload2, fx2, env=_Env("d2", "c2"), engine=_Engine(), event_store=es)

    assert fx2.messages
    assert "cooldown/gate" in str(fx2.messages[-1].get("text") or "")
