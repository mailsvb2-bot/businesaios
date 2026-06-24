from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Sequence

from runtime.monetization import RevenueAdvisoryService
from runtime.monetization import RevenueDecisionEnvelope as RuntimeRevenueDecisionEnvelope
from runtime.monetization import RevenuePaywallVariantInput
from runtime.monetization import RevenuePlanInput
from runtime.monetization import RevenueSnapshotInput

CANON_EXECUTION_REVENUE_OS_ADAPTER = True


@dataclass(frozen=True, slots=True)
class ExecutionRevenueDecisionEnvelope:
    world_state_patch: dict[str, Any]
    candidate_actions: tuple[dict[str, Any], ...]
    experiments: tuple[dict[str, Any], ...]
    action_mappings: tuple[dict[str, Any], ...]
    audit_records: tuple[dict[str, Any], ...]
    explain: dict[str, Any] = field(default_factory=dict)


class RevenueOSAdapter:
    """Thin adapter that emits advisory evidence for the canonical DecisionCore path only.

    This adapter does not execute actions, open network connections, mutate provider state,
    or bypass the project's single decision owner. It stays in advisory_only mode.
    """

    def __init__(self, *, service: RevenueAdvisoryService | None = None) -> None:
        self._service = service or RevenueAdvisoryService()

    def build_envelope(
        self,
        *,
        tenant_id: str,
        product_id: str,
        snapshots: Sequence[RevenueSnapshotInput],
        plans: Sequence[RevenuePlanInput],
        paywall_variants: Sequence[RevenuePaywallVariantInput],
        target_cac: float | None = None,
    ) -> ExecutionRevenueDecisionEnvelope:
        envelope = self._service.build_envelope(
            tenant_id=tenant_id,
            product_id=product_id,
            snapshots=snapshots,
            plans=plans,
            paywall_variants=paywall_variants,
            target_cac=target_cac,
        )
        return self._to_execution_envelope(envelope)

    def _to_execution_envelope(self, envelope: RuntimeRevenueDecisionEnvelope) -> ExecutionRevenueDecisionEnvelope:
        candidate_actions = tuple(
            {
                'action_type': item.action_type,
                'kind': item.kind,
                'confidence': item.confidence,
                'payload': dict(item.payload),
                'evidence': dict(item.evidence),
                'reason_codes': list(item.reason_codes),
                'blast_radius': item.blast_radius,
                'requires_approval': item.requires_approval,
                'owner': item.owner,
            }
            for item in envelope.candidate_actions
        )
        experiments = tuple(
            {
                'experiment_id': item.experiment_id,
                'kind': item.kind,
                'hypothesis': item.hypothesis,
                'metric_primary': item.metric_primary,
                'metric_guardrails': list(item.metric_guardrails),
                'arms': tuple(dict(arm) for arm in item.arms),
                'holdout_allocation': item.holdout_allocation,
                'max_daily_exposure': item.max_daily_exposure,
                'created_at': item.created_at,
                'metadata': dict(item.metadata),
            }
            for item in envelope.experiments
        )
        action_mappings = tuple(
            {
                'catalog_action': item.catalog_action,
                'mode': item.mode,
                'payload': dict(item.payload),
                'confidence': item.confidence,
                'owner': item.owner,
            }
            for item in envelope.action_mappings
        )
        explain = dict(envelope.explain)
        return ExecutionRevenueDecisionEnvelope(
            world_state_patch=dict(envelope.world_state_patch),
            candidate_actions=candidate_actions,
            experiments=experiments,
            action_mappings=action_mappings,
            audit_records=tuple(dict(item) for item in envelope.audit_records),
            explain=explain,
        )


RevenueDecisionEnvelope = ExecutionRevenueDecisionEnvelope

__all__ = ['CANON_EXECUTION_REVENUE_OS_ADAPTER', 'RevenueDecisionEnvelope', 'RevenueOSAdapter']
