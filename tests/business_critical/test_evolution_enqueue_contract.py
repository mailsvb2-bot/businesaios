from __future__ import annotations

from types import SimpleNamespace

import pytest

import runtime.evolution as evolution_runtime
from runtime._internal.effects_domains import evolution as evolution_module
from runtime._internal.effects_domains.evolution import EvolutionEffectsMixin
from runtime.platform.outbox.sqlite_evolution_outbox import SqliteEvolutionOutbox


class FakeEventLog:
    tenant_id = "business-a"

    def __init__(self) -> None:
        self.events: list[dict] = []
        self.fail_next_emit = False

    def emit(self, **event):
        if self.fail_next_emit:
            self.fail_next_emit = False
            raise RuntimeError("audit event unavailable")
        event_id = str(event.get("event_id") or "")
        if any(str(item.get("event_id") or "") == event_id for item in self.events):
            raise RuntimeError("duplicate event_id")
        self.events.append(dict(event))
        return SimpleNamespace(event_id=event_id)

    def get_events(self, decision_id: str, event_type: str) -> list[dict]:
        return [
            dict(event)
            for event in self.events
            if str(event.get("decision_id") or "") == str(decision_id)
            and str(event.get("event_type") or "") == str(event_type)
        ]


class FakeOutbox:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.jobs: dict[str, dict] = {}

    def enqueue(self, *, job_kind: str, payload: dict, job_id: str | None = None):
        job = str(job_id or "")
        call = {
            "job_id": job,
            "job_kind": str(job_kind),
            "payload": dict(payload),
        }
        self.calls.append(call)
        existing = self.jobs.get(job)
        if existing is not None and existing != call:
            raise RuntimeError("EVOLUTION_JOB_ID_CONFLICT")
        self.jobs[job] = call
        return job


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

    assert len(fake_outbox.calls) == 1
    call = fake_outbox.calls[0]
    assert call["job_id"]
    assert call["job_kind"] == "offer_analysis"
    assert call["payload"] == {
        "tenant_id": "business-a",
        "requested_by": "owner-1",
        "decision_id": "decision-evolution-1",
        "correlation_id": "correlation-evolution-1",
        "input_ref": "offer-7",
    }
    event = effects.event_log.events[-1]
    assert event["event_type"] == "evolution_job_enqueued"
    assert event["payload"] == {
        "tenant_id": "business-a",
        "job_id": call["job_id"],
        "job_kind": "offer_analysis",
    }
    assert result["ok"] is True
    assert result["job_id"] == call["job_id"]
    assert result["router_evidence"]["source"] == "ledger"
    assert result["router_evidence"]["external_refs"] == [event["event_id"]]


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
def test_audit_failure_retry_reuses_one_job_and_one_event(fake_outbox: FakeOutbox) -> None:
    effects = FakeEffects()
    effects.event_log.fail_next_emit = True
    kwargs = {
        "decision_id": "decision-evolution-retry",
        "correlation_id": "correlation-evolution-retry",
        "tenant_id": "business-a",
        "user_id": "owner-1",
        "job_kind": "offer_analysis",
        "payload": {"input_ref": "offer-7"},
    }

    with pytest.raises(RuntimeError, match="audit event unavailable"):
        effects.enqueue_evolution_job(**kwargs)

    assert len(fake_outbox.jobs) == 1
    first_job_id = fake_outbox.calls[0]["job_id"]
    assert effects.event_log.events == []

    second = effects.enqueue_evolution_job(**kwargs)
    third = effects.enqueue_evolution_job(**kwargs)

    assert [call["job_id"] for call in fake_outbox.calls] == [
        first_job_id,
        first_job_id,
        first_job_id,
    ]
    assert len(fake_outbox.jobs) == 1
    assert len(effects.event_log.events) == 1
    assert second["job_id"] == first_job_id
    assert third["job_id"] == first_job_id
    assert second["router_evidence"] == third["router_evidence"]


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

    assert len(fake_outbox.jobs) == 1
    assert effects.messages[-1]["tenant_id"] == "business-a"
    assert effects.messages[-1]["user_id"] == "admin-2"
    assert result["ok"] is True
    assert result["notification"] is None
    assert result["router_evidence"]["external_refs"] == [
        effects.event_log.events[-1]["event_id"]
    ]


@pytest.mark.lock
def test_sqlite_outbox_retry_never_resets_completed_job_or_accepts_conflicting_payload(tmp_path) -> None:
    outbox = SqliteEvolutionOutbox(str(tmp_path / "evolution.db"))
    job_id = "stable-job-1"

    assert outbox.enqueue(
        job_id=job_id,
        job_kind="offer_analysis",
        payload={"tenant_id": "business-a", "input_ref": "offer-7"},
    ) == job_id
    outbox.mark_done(job_id)

    assert outbox.enqueue(
        job_id=job_id,
        job_kind="offer_analysis",
        payload={"input_ref": "offer-7", "tenant_id": "business-a"},
    ) == job_id
    assert outbox.get_status(job_id) == "done"
    assert outbox.count_pending() == 0

    with pytest.raises(RuntimeError, match="EVOLUTION_JOB_ID_CONFLICT"):
        outbox.enqueue(
            job_id=job_id,
            job_kind="offer_analysis",
            payload={"tenant_id": "business-a", "input_ref": "different-offer"},
        )
