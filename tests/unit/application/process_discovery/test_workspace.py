from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from application.process_discovery import (
    AgentBlueprint,
    CanonicalProcessWorkspace,
    ComparisonEvidence,
    DiscoverBuildMeasureService,
    DiscoveryPolicy,
    InterventionProof,
    InterventionSpend,
    ProcessBaseline,
    ProcessObservation,
)

BASE = datetime(2026, 8, 1, tzinfo=UTC)


def sample(*, start: int = 0, minutes: int = 45) -> list[ProcessObservation]:
    return [
        ProcessObservation(
            tenant_id="t1",
            business_id="b1",
            process_key="client_followup",
            occurred_at=BASE + timedelta(days=start + index),
            source="canonical_crm_events",
            evidence_id=f"ev-{start}-{index}",
            manual_minutes=minutes,
            actor_cost_per_hour_minor=40_000,
            direct_loss_minor=1_000,
            revenue_at_risk_minor=0,
            currency="RUB",
            automation_fit=0.9,
            operational_risk=0.1,
        )
        for index in range(6)
    ]


@dataclass
class EvidenceSource:
    items: list[ProcessObservation]

    def load_process_observations(self, *, tenant_id: str, business_id: str):
        assert tenant_id == "t1" and business_id == "b1"
        return tuple(self.items)


@dataclass
class Ledger:
    records: dict[str, tuple[AgentBlueprint, ProcessBaseline]] = field(default_factory=dict)

    def save(self, *, blueprint: AgentBlueprint, baseline: ProcessBaseline) -> None:
        self.records[blueprint.blueprint_id] = (blueprint, baseline)

    def get(self, *, tenant_id: str, business_id: str, blueprint_id: str):
        record = self.records.get(blueprint_id)
        if not record:
            return None
        blueprint, _ = record
        if blueprint.tenant_id != tenant_id or blueprint.business_id != business_id:
            return None
        return record


@dataclass
class MeasurementSource:
    after: list[ProcessObservation]
    verified: bool = True

    def load_intervention_proof(self, *, tenant_id: str, business_id: str, blueprint: AgentBlueprint):
        if not self.verified:
            return None
        return InterventionProof(
            tenant_id=tenant_id,
            business_id=business_id,
            blueprint_id=blueprint.blueprint_id,
            intervention_id="int-1",
            started_at=BASE + timedelta(days=15),
            server_validated=True,
            execution_verified=True,
            run_id="run-1",
            decision_id="decision-1",
            action_id="action-1",
            evidence_refs=("proof-1",),
        )

    def load_after_observations(self, *, tenant_id: str, business_id: str, blueprint: AgentBlueprint, intervention):
        return tuple(self.after)

    def load_intervention_spend(self, *, tenant_id: str, business_id: str, blueprint: AgentBlueprint, intervention):
        return InterventionSpend(ai_runtime_cost_minor=1_000, currency="RUB")

    def load_comparison_evidence(self, *, tenant_id: str, business_id: str, blueprint: AgentBlueprint, intervention):
        return ComparisonEvidence()


def workspace(*, verified: bool = True) -> CanonicalProcessWorkspace:
    return CanonicalProcessWorkspace(
        service=DiscoverBuildMeasureService(DiscoveryPolicy(min_observations=5, min_window_days=5, min_confidence=0.2)),
        evidence_source=EvidenceSource(sample()),
        blueprint_ledger=Ledger(),
        measurement_source=MeasurementSource(sample(start=20, minutes=5), verified=verified),
    )


def test_workspace_roundtrip_uses_server_sources_and_string_goal_contract() -> None:
    api = workspace()
    discovery = api.discover(tenant_id="t1", business_id="b1")
    built = api.build(
        tenant_id="t1",
        business_id="b1",
        opportunity_id=discovery["opportunities"][0]["opportunity_id"],
        payload={
            "owner_goal": "Сократить ручной follow-up",
            "requested_capabilities": ["crm_read", "communications_draft"],
            "manual_minutes_per_30d": 0,
            "claimed_roi": 9999,
        },
    )
    assert isinstance(built["decisioncore_goal"], str)
    assert built["execution_created"] is False
    assert built["measurement_ready"] is False
    advisory = api.decision_request(tenant_id="t1", business_id="b1", blueprint_id=built["blueprint"]["blueprint_id"])
    assert advisory["objective"] == "Сократить ручной follow-up"
    assert advisory["metadata"]["executable"] is False
    measured = api.measure(tenant_id="t1", business_id="b1", blueprint_id=built["blueprint"]["blueprint_id"])
    assert measured["status"] == "ok"
    assert measured["measurement_ready"] is True
    assert measured["measurement"]["causal_claim_allowed"] is False


def test_workspace_measure_is_fail_closed_until_server_verified_intervention_exists() -> None:
    api = workspace(verified=False)
    discovery = api.discover(tenant_id="t1", business_id="b1")
    built = api.build(
        tenant_id="t1",
        business_id="b1",
        opportunity_id=discovery["opportunities"][0]["opportunity_id"],
        payload={"owner_goal": "Сократить ручной follow-up"},
    )
    measured = api.measure(tenant_id="t1", business_id="b1", blueprint_id=built["blueprint"]["blueprint_id"])
    assert measured == {
        "blueprint_id": built["blueprint"]["blueprint_id"],
        "status": "intervention_not_verified",
        "measurement": None,
        "measurement_ready": False,
    }
