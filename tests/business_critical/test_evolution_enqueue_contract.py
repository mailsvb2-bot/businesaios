from __future__ import annotations

from types import SimpleNamespace

import pytest

import runtime.evolution as evolution_runtime
from runtime._internal.effects_domains import evolution as evolution_module
from runtime._internal.effects_domains.evolution import EvolutionEffectsMixin


class FakeEventLog:
    tenant_id = "business-a"

    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, **event):
        self.events.append(dict(event))
        return SimpleNamespace(event_id="event-evolution-1")


class FakeOutbox:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def enqueue(self, *, job_kind: str, payload: dict):
        self.calls.append({"job_kind": job_kind, "payload": dict(payload)})
        return "job-42"


class FakeEffects(EvolutionEffectsMixin):
    def __init__(self, *, notification_fails: bool = False) -> None:
        self.event_log = FakeEventLog()
        self.notification_fails = notification_fails
        self.messages: list[dict] = []

    def send_message(self, **kwargs):
        self.messages.append(dict(kwargs))
        if self.notification_fails:
            raise RuntimeError("telegram unavailable")
        return {
            "ok": True,
            "evidence": {
                "source": "connector",
                "verified": True,
                "status": "verified",
                "external_refs": ["message-1"],
                "confidence": 1.0,
            },
        }


@pytest.fixture
def fake_outbox(monkeypatch: pytest.MonkeyPatch) -> FakeOutbox:
    outbox = FakeOutbox()

    class FakeEvolutionOutbox:
        @classmethod
        def from_env(cls):
            return outbox

    monkeypatch.setattr(evolution_module, "assert_called_from_executor", lambda: None)
    monkeypatch.setattr(evolution_runtime, "EvolutionOutbox", FakeEvolutionOutbox)
    return outbox


@pytest.mark.lock
def test_evolution_enqueue_seals_tenant_and_decision_causality(fake_outbox: FakeOutbox) -> None:
    effects = FakeEffects()

    result = effects.enqueue_evolution_job(
        decision_id="decision-evolution-1",
        correlation_id="correlation-evolution-1",
        tenant_id="business-a",
        user_id="owner-1",
        job_kind="offer_analysis",
        payload={
            "tenant_id": "attacker-business",
            "requested_by": "forged-user",
            "decision_id": "forged-decision",
            "correlation_id": "forged-correlation",
            "input_ref": "offer-7",
        },
    )

    assert fake_outbox.calls == [
        {
            "job_kind": "offer_analysis",
            "payload": {
                "tenant_id": "business-a",
                "requested_by": "owner-1",
                "decision_id": "decision-evolution-1",
                "correlation_id": "correlation-evolution-1",
                "input_ref": "offer-7",
            },
        }
    ]
    assert effects.event_log.events[-1]["event_type"] == "evolution_job_enqueued"
    assert effects.event_log.events[-1]["payload"] == {
        "tenant_id": "business-a",
        "job_id": "job-42",
        "job_kind": "offer_analysis",
    }
    assert result["ok"] is True
    assert result["status"] == "verified"
    assert result["router_evidence"]["source"] == "ledger"
    assert result["router_evidence"]["external_refs"] == ["event-evolution-1"]


@pytest.mark.lock
def test_evolution_enqueue_rejects_cross_tenant_execution_before_outbox_write(fake_outbox: FakeOutbox) -> None:
    effects = FakeEffects()

    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        effects.enqueue_evolution_job(
            decision_id="decision-evolution-2",
            correlation_id="correlation-evolution-2",
            tenant_id="business-b",
            user_id="owner-1",
            job_kind="offer_analysis",
            payload={},
        )

    assert fake_outbox.calls == []
    assert effects.event_log.events == []


@pytest.mark.lock
def test_notification_failure_does_not_erase_durable_evolution_enqueue_proof(fake_outbox: FakeOutbox) -> None:
    effects = FakeEffects(notification_fails=True)

    result = effects.enqueue_evolution_job(
        decision_id="decision-evolution-3",
        correlation_id="correlation-evolution-3",
        tenant_id="business-a",
        user_id="owner-1",
        job_kind="offer_analysis",
        payload={
            "notify_text": "Задача поставлена",
            "notify_user_id": "admin-2",
        },
    )

    assert len(fake_outbox.calls) == 1
    assert effects.messages[-1]["tenant_id"] == "business-a"
    assert effects.messages[-1]["user_id"] == "admin-2"
    assert result["ok"] is True
    assert result["notification"] is None
    assert result["router_evidence"]["external_refs"] == ["event-evolution-1"]
