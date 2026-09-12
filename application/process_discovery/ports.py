from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .contracts import (
    AgentBlueprint,
    ComparisonEvidence,
    InterventionProof,
    InterventionSpend,
    ProcessBaseline,
    ProcessObservation,
)


class TrustedProcessEvidenceSource(Protocol):
    def load_process_observations(self, *, tenant_id: str, business_id: str) -> Sequence[ProcessObservation]: ...


class ProcessEvidenceRecorder(Protocol):
    def record_owner_observation(self, *, tenant_id: str, business_id: str, user_id: str | None, payload: dict, request_id: str | None = None) -> ProcessObservation: ...


class ProcessDecisionBindingStore(Protocol):
    def record_decision_result(self, *, tenant_id: str, business_id: str, blueprint: AgentBlueprint, result: dict) -> dict: ...


class BlueprintLedger(Protocol):
    def save(self, *, blueprint: AgentBlueprint, baseline: ProcessBaseline) -> None: ...

    def get(
        self,
        *,
        tenant_id: str,
        business_id: str,
        blueprint_id: str,
    ) -> tuple[AgentBlueprint, ProcessBaseline] | None: ...


class TrustedMeasurementSource(Protocol):
    def load_intervention_proof(
        self,
        *,
        tenant_id: str,
        business_id: str,
        blueprint: AgentBlueprint,
    ) -> InterventionProof | None: ...

    def load_after_observations(
        self,
        *,
        tenant_id: str,
        business_id: str,
        blueprint: AgentBlueprint,
        intervention: InterventionProof,
    ) -> Sequence[ProcessObservation]: ...

    def load_intervention_spend(
        self,
        *,
        tenant_id: str,
        business_id: str,
        blueprint: AgentBlueprint,
        intervention: InterventionProof,
    ) -> InterventionSpend: ...

    def load_comparison_evidence(
        self,
        *,
        tenant_id: str,
        business_id: str,
        blueprint: AgentBlueprint,
        intervention: InterventionProof,
    ) -> ComparisonEvidence: ...


__all__ = ["BlueprintLedger", "ProcessDecisionBindingStore", "ProcessEvidenceRecorder", "TrustedMeasurementSource", "TrustedProcessEvidenceSource"]
