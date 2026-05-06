from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from execution.revenue_os_adapter import RevenueDecisionEnvelope, RevenueOSAdapter
from runtime.monetization import RevenueAdvisoryStoreWiring, build_revenue_advisory_store_wiring
from runtime.monetization import RevenueAdvisoryService
from runtime.monetization import RevenuePaywallVariantInput
from runtime.monetization import RevenuePlanInput
from runtime.monetization import RevenueSnapshotInput
from runtime.monetization import persist_revenue_advisory_envelope

CANON_EXECUTION_REVENUE_OS_RUNTIME = True


@dataclass(frozen=True)
class RevenueOSRuntimeResult:
    envelope: RevenueDecisionEnvelope
    audit_records: tuple[dict[str, Any], ...]
    persisted: dict[str, int]


@dataclass
class RevenueOSRuntime:
    wiring: RevenueAdvisoryStoreWiring = field(default_factory=build_revenue_advisory_store_wiring)
    service: RevenueAdvisoryService = field(default_factory=RevenueAdvisoryService)

    def __post_init__(self) -> None:
        self.adapter = RevenueOSAdapter(service=self.service)

    def analyze(
        self,
        *,
        tenant_id: str,
        product_id: str,
        snapshots: Sequence[RevenueSnapshotInput],
        plans: Sequence[RevenuePlanInput],
        paywall_variants: Sequence[RevenuePaywallVariantInput],
        target_cac: float | None = None,
    ) -> RevenueOSRuntimeResult:
        runtime_envelope = self.service.build_envelope(
            tenant_id=tenant_id,
            product_id=product_id,
            snapshots=snapshots,
            plans=plans,
            paywall_variants=paywall_variants,
            target_cac=target_cac,
        )
        persisted = persist_revenue_advisory_envelope(
            wiring=self.wiring,
            tenant_id=tenant_id,
            product_id=product_id,
            envelope=runtime_envelope,
        )
        envelope = self.adapter._to_execution_envelope(runtime_envelope)
        return RevenueOSRuntimeResult(
            envelope=envelope,
            audit_records=tuple(dict(item) for item in envelope.audit_records),
            persisted=dict(persisted),
        )


__all__ = ['CANON_EXECUTION_REVENUE_OS_RUNTIME', 'RevenueOSRuntime', 'RevenueOSRuntimeResult']
