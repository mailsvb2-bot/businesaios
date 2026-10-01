from __future__ import annotations

import time

from application.business_discovery import (
    OwnerBusinessAssertion,
    OwnerBusinessAssertionIngress,
    ProviderBusinessObservationIngress,
)
from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel
from core.ai.decision_core import DecisionCore
from core.ai.policy_registry import PolicyRegistry
from core.ai.schema_registry import DecisionSchema, SchemaRegistry
from core.ai.snapshot_store import MemorySnapshotStore
from core.ai.world_state import WorldStateV1
from core.events.log import EventLog
from core.policies.selector import PolicySelector
from core.security.keyring import Keyring
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.provider_runtime_audit import ProviderRuntimeAuditRecorder
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.state import StateSynthesisEngine
from runtime.state.state_snapshot_store import FileStateSnapshotStore
from storage.audit_store import InMemoryAuditStore
from storage.evidence_store import InMemoryEvidenceStore


class _BusinessAwarePolicy:
    id = "business-discovery-acceptance@v1"

    def propose(self, state):
        view = state.world_model_semantics
        industry = next(
            (record.value for record in view.records if record.key == "business.profile.industry"),
            "unknown",
        )
        return type(
            "_Proposal",
            (),
            {
                "action": "send_message@v1",
                "payload": {"user_id": "owner-1", "text": f"industry:{industry}"},
            },
        )()


def _decision_core(state_store) -> DecisionCore:
    schemas = SchemaRegistry()
    schemas.register(
        "send_message@v1",
        1,
        DecisionSchema(
            required={"user_id", "text"},
            optional=set(),
            field_types={"user_id": str, "text": str},
        ),
    )
    registry = PolicyRegistry()
    registry.register(_BusinessAwarePolicy())
    return DecisionCore(
        PolicySelector(registry),
        Keyring({"k1": {"secret": b"secret", "revoked": False}}, "k1"),
        schemas,
        MemorySnapshotStore(),
        EventLog(MemoryEventStore(), tenant="tenant-1"),
        world_model=CanonicalDecisionWorldModel(
            store=object(),
            kind="ltv@v1",
            state_snapshot_store=state_store,
        ),
    )


def _world_state(now_ms: int) -> WorldStateV1:
    return WorldStateV1(
        schema_version=1,
        tenant_id="tenant-1",
        user={"user_id": "owner-1"},
        session={"channel": "headless"},
        product={"business_id": "business-1"},
        economy={},
        timestamp_ms=now_ms,
        user_id="owner-1",
    )


def test_owner_truth_provider_reconciliation_changes_next_sovereign_decision(
    tmp_path, monkeypatch
) -> None:
    import application.decision_runtime.runtime as decision_runtime

    monkeypatch.setattr(
        decision_runtime,
        "gate_action_or_raise",
        lambda **kwargs: (True, "ok", {}),
    )
    events = MemoryEventStore()
    evidence = InMemoryEvidenceStore()
    state = StateSynthesisEngine(
        snapshot_store=FileStateSnapshotStore(tmp_path / "state")
    )
    owner = OwnerBusinessAssertionIngress(
        event_store=events,
        evidence_store=evidence,
        state_engine=state,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    provider = ProviderBusinessObservationIngress(
        event_store=events,
        evidence_store=evidence,
        state_engine=state,
    )
    audit = ProviderRuntimeAuditRecorder(
        audit_store=InMemoryAuditStore(),
        evidence_store=evidence,
    )
    now_ms = int(time.time() * 1000)
    owner.ingest(
        assertion=OwnerBusinessAssertion(
            tenant_id="tenant-1",
            business_id="business-1",
            actor_id="owner-1",
            field_key="identity.industry",
            value="medical_services",
            observed_at_ms=now_ms,
        ),
        idempotency_key="owner-industry-medical",
        recorded_at_ms=now_ms,
    )

    core = _decision_core(state.snapshot_store)
    before = core.issue(_world_state(now_ms))
    assert before.decision.payload["text"] == "industry:medical_services"

    provider_evidence = audit.record_sync_run(
        tenant_id="tenant-1",
        business_id="business-1",
        provider_key="hubspot",
        operation="contact_sync",
        mode="live",
        status="live_executed",
        accepted=True,
        payload={},
        metadata={
            "business_observations": [
                {"field_key": "identity.industry", "value": "retail"}
            ]
        },
    )
    result = provider.reconcile(
        tenant_id="tenant-1",
        business_id="business-1",
        evidence_id=provider_evidence["evidence_id"],
    )
    assert result.conflicted_fields == ("identity.industry",)

    after = core.issue(_world_state(now_ms + 1))
    assert after.decision.payload["text"] == "industry:retail"
    assert after.decision.decision_id != before.decision.decision_id
