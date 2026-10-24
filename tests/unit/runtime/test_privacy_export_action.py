from __future__ import annotations

from types import SimpleNamespace

from core.actions.catalog_groups import governance_catalog
from core.events.event_types import is_known
from core.policies.telegram.routes.command_routes import handle_command_routes
from runtime.boot_impl.actions_catalog import SPEC_ROWS
from runtime.handler_impl.domains.user_ops import handle_privacy_export


class _Store:
    def __init__(self, events):
        self.events = events
        self.calls = []

    def iter_events(self, *, tenant_id, start_ms, end_ms=None, user_id=None, event_type=None):
        self.calls.append((tenant_id, user_id))
        return [e for e in self.events if e["tenant_id"] == tenant_id and e["user_id"] == user_id]

    def delete_user_events(self, **kwargs):  # never called by export
        raise AssertionError("export must not delete")


class _Effects:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, []

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return {"ok": self.ok, "router_evidence": {"source": "telegram", "message_id": 1}}


ENV = SimpleNamespace(decision=SimpleNamespace(decision_id="d1", correlation_id="c1"))
EVENTS = [
    {"tenant_id": "t1", "user_id": "u1", "event_type": "mood_logged"},
    {"tenant_id": "t1", "user_id": "u1", "event_type": "mood_logged"},
    {"tenant_id": "t1", "user_id": "u2", "event_type": "secret_of_other_user"},
    {"tenant_id": "t2", "user_id": "u1", "event_type": "other_tenant"},
]


def test_export_is_scoped_to_requester_and_tenant() -> None:
    effects = _Effects()
    out = handle_privacy_export({"tenant_id": "t1", "user_id": "u1"}, effects, ENV, event_store=_Store(EVENTS))
    assert out["ok"] is True
    sent = effects.calls[0]
    assert sent["user_id"] == "u1" and "mood_logged: 2" in sent["text"]
    assert "secret_of_other_user" not in sent["text"] and "other_tenant" not in sent["text"]
    assert sent["track_event_type"] == "privacy_export@v1"


def test_failed_read_or_delivery_is_not_success() -> None:
    class Broken(_Store):
        def iter_events(self, **kwargs):
            raise RuntimeError("db down")

    effects = _Effects()
    out = handle_privacy_export({"tenant_id": "t1", "user_id": "u1"}, effects, ENV, event_store=Broken([]))
    assert out["ok"] is False and effects.calls[0]["track_event_type"] == "privacy_export_failed@v1"
    out = handle_privacy_export({"tenant_id": "t1", "user_id": "u1"}, _Effects(ok=False), ENV, event_store=_Store(EVENTS))
    assert out["ok"] is False


def test_action_is_registered_once_and_routed_from_telegram_command() -> None:
    assert "privacy_export@v1" in governance_catalog()
    assert [r[0] for r in SPEC_ROWS if isinstance(r, tuple)].count("privacy_export@v1") == 1
    assert is_known("privacy_export@v1") and is_known("privacy_export_failed@v1")
    ctx = SimpleNamespace(cmd="/export_data", args="", callback_data=None, autopilot_dashboard={})
    proposed = handle_command_routes(ctx, user_id="u1", pm=lambda **kw: kw)
    assert proposed.action == "privacy_export@v1" and proposed.payload["user_id"] == "u1"


def test_privacy_export_passes_operational_budget_without_human_approval(tmp_path) -> None:
    from contracts.action_impact_contract import ActionExecutionContext
    from core.safety.operational.factory import build_persistent_operational_safety_runtime

    runtime = build_persistent_operational_safety_runtime(storage_path=tmp_path / "ledger.json", policy_provider=None)
    result = runtime.service.precheck(
        ActionExecutionContext(
            tenant_id="t1",
            user_id="42",
            action_name="privacy_export@v1",
            payload={"user_id": "42"},
            metadata={},
            execution_id="exec-1",
        )
    )
    assert result.decision.status == "allow"
    assert result.impact.requires_human_approval is False
