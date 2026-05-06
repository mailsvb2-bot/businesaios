from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.world_model.builders.business_state_builder import BusinessStateBuilder
from core.world_model.builders.customer_state_builder import CustomerStateBuilder
from core.world_model.builders.demand_state_builder import DemandStateBuilder
from core.world_model.builders.market_state_builder import MarketStateBuilder
from core.world_model.builders.product_state_builder import ProductStateBuilder
from core.world_model.contracts import (
    WORLD_SNAPSHOT_DECISION_ISSUER,
    WORLD_SNAPSHOT_READ_ONLY,
    WORLD_SNAPSHOT_ROLE,
)
from core.world_model.enums import SnapshotRejectionReason
from core.world_model.errors import WorldModelGuardError
from core.world_model.events.snapshot_built import WorldSnapshotBuilt
from core.world_model.events.snapshot_rejected import WorldSnapshotRejected
from core.world_model.explainers.confidence_explainer import ConfidenceExplainer
from core.world_model.explainers.state_gap_explainer import StateGapExplainer
from core.world_model.explainers.world_snapshot_explainer import WorldSnapshotExplainer
from core.world_model.types import ReaderBundle, SnapshotRejection, StateBundle, WorldModelBuildInput, WorldSnapshot


class _NoopPublisher:
    def publish_snapshot_built(self, snapshot: WorldSnapshot) -> None:
        _ = snapshot

    def publish_snapshot_rejected(self, rejection: SnapshotRejection) -> None:
        _ = rejection


class WorldModelStateAssembler:
    def __init__(self) -> None:
        self._customer_builder = CustomerStateBuilder()
        self._product_builder = ProductStateBuilder()
        self._demand_builder = DemandStateBuilder()
        self._market_builder = MarketStateBuilder()
        self._business_builder = BusinessStateBuilder()

    def build_state_bundle(self, *, build_input: WorldModelBuildInput, readers: ReaderBundle) -> StateBundle:
        customer_state = self._customer_builder.build(readers.customer.payload)
        product_state = self._product_builder.build(readers.product.payload)
        demand_state = self._demand_builder.build(
            revenue_payload=readers.revenue.payload,
            campaign_payload=readers.campaign.payload,
            market_payload=readers.market.payload,
            messaging_payload=readers.messaging.payload,
        )
        market_state = self._market_builder.build(
            market_payload=readers.market.payload,
            campaign_payload=readers.campaign.payload,
            messaging_payload=readers.messaging.payload,
            channel=build_input.channel,
            geo=build_input.geo,
        )
        business_state = self._business_builder.build(
            tenant_id=build_input.tenant_id,
            business_id=build_input.business_id,
            customer=customer_state,
            product=product_state,
            demand=demand_state,
            market=market_state,
            messaging_payload=readers.messaging.payload,
            revenue_payload=readers.revenue.payload,
        )
        return StateBundle(business_state=business_state)


class WorldModelSnapshotSupport:
    def __init__(self) -> None:
        self._snapshot_explainer = WorldSnapshotExplainer()
        self._state_gap_explainer = StateGapExplainer()
        self._confidence_explainer = ConfidenceExplainer()

    def build_explain(self, *, freshness: Any, completeness: Any, confidence_report: Any) -> dict[str, Any]:
        return {
            "gaps": self._state_gap_explainer.explain(completeness=completeness),
            "confidence": self._confidence_explainer.explain(
                confidence=confidence_report,
                freshness=freshness,
            ),
            "contract": _snapshot_contract(),
        }

    def build_metadata(self, *, readers: ReaderBundle) -> dict[str, Any]:
        return {
            "sources": {
                "customer": readers.customer.source,
                "revenue": readers.revenue.source,
                "campaign": readers.campaign.source,
                "product": readers.product.source,
                "messaging": readers.messaging.source,
                "market": readers.market.source,
            },
            "contract": _snapshot_contract(),
        }

    def extend_snapshot_explain(self, *, snapshot: WorldSnapshot) -> WorldSnapshot:
        explain = dict(snapshot.explain)
        explain["snapshot"] = self._snapshot_explainer.explain(snapshot=snapshot)
        return replace(snapshot, explain=explain)

    def extend_snapshot_metadata(
        self,
        *,
        snapshot: WorldSnapshot,
        snapshot_built_event: WorldSnapshotBuilt,
    ) -> WorldSnapshot:
        metadata = dict(snapshot.metadata)
        metadata["events"] = {
            "snapshot_built_event_id": snapshot_built_event.event_id,
            "snapshot_built_event_type": snapshot_built_event.event_type,
        }
        return replace(snapshot, metadata=metadata)

    def build_snapshot_built_event(self, *, snapshot: WorldSnapshot) -> WorldSnapshotBuilt:
        return WorldSnapshotBuilt.create(
            snapshot_id=snapshot.snapshot_id,
            tenant_id=snapshot.tenant_id,
            business_id=snapshot.business_id,
            built_at_ms=snapshot.built_at_ms,
            payload={"confidence_score": snapshot.confidence},
        )

    def build_snapshot_rejected_event(
        self,
        *,
        snapshot_id: str,
        tenant_id: str,
        business_id: str,
        built_at_ms: int,
        exc: WorldModelGuardError,
        freshness: Any,
        completeness: Any,
    ) -> WorldSnapshotRejected:
        return WorldSnapshotRejected.create(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            business_id=business_id,
            built_at_ms=built_at_ms,
            reason=map_rejection_reason(exc),
            payload={
                "error": exc.__class__.__name__,
                "message": exc.__class__.__name__,
                "freshness": {k: v.value for k, v in freshness.per_reader.items()},
                "missing_fields": list(completeness.missing_fields),
            },
        )

    def build_rejection(
        self,
        *,
        build_input: WorldModelBuildInput,
        snapshot_id: str,
        built_at_ms: int,
        exc: WorldModelGuardError,
        freshness: Any,
        completeness: Any,
        rejection_event: WorldSnapshotRejected,
    ) -> SnapshotRejection:
        return SnapshotRejection(
            snapshot_id=snapshot_id,
            tenant_id=build_input.tenant_id,
            business_id=build_input.business_id,
            built_at_ms=built_at_ms,
            schema_version="world_snapshot@v1",
            reason=map_rejection_reason(exc),
            details={
                "error": exc.__class__.__name__,
                "message": exc.__class__.__name__,
                "event_id": rejection_event.event_id,
                "event_type": rejection_event.event_type,
                "freshness": {k: v.value for k, v in freshness.per_reader.items()},
                "missing_fields": list(completeness.missing_fields),
            },
        )


def map_rejection_reason(exc: WorldModelGuardError) -> str:
    name = exc.__class__.__name__
    if name == "StaleSignalError":
        return SnapshotRejectionReason.STALE_SIGNAL.value
    if name == "IncompleteStateError":
        return SnapshotRejectionReason.INCOMPLETE_STATE.value
    return SnapshotRejectionReason.INTEGRITY_VIOLATION.value


def _snapshot_contract() -> dict[str, Any]:
    return {
        "read_only": WORLD_SNAPSHOT_READ_ONLY,
        "decision_issuer": WORLD_SNAPSHOT_DECISION_ISSUER,
        "role": WORLD_SNAPSHOT_ROLE,
    }


__all__ = [
    "_NoopPublisher",
    "WorldModelStateAssembler",
    "WorldModelSnapshotSupport",
    "map_rejection_reason",
]
