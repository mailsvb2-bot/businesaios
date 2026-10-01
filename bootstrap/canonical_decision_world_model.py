from __future__ import annotations

from runtime.state.state_contract import StateSnapshotStorePort

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_CLUSTER_FINAL_OWNER = True

from dataclasses import replace
from typing import Any, Optional

from runtime.platform.economics.world_model_store_contracts import WorldModelStorePort
from runtime.platform.economics.world_model_store_factory import build_world_model_store
from bootstrap.canonical_decision_world_model_ltv import CanonicalLtvEnricher, LtvInput
from bootstrap.canonical_decision_world_model_pricing import enrich_pricing
from bootstrap.canonical_decision_world_model_resolvers import safe_dict
from ports.world_model import DecisionWorldModelPort


class CanonicalDecisionWorldModel(DecisionWorldModelPort):
    """Single adapter that enriches state for DecisionCore.

    It enriches state.
    It pins world-model metadata.
    It does not decide.
    """

    def __init__(
        self,
        *,
        store: Optional[WorldModelStorePort] = None,
        kind: str = "hybrid@v1",
        state_snapshot_store: StateSnapshotStorePort | None = None,
    ) -> None:
        self._store = store or build_world_model_store()
        self._state_snapshot_store = state_snapshot_store
        self._kind = str(kind or "hybrid@v1").strip().lower()
        self._ltv = CanonicalLtvEnricher()

    def enrich_state(self, state: Any) -> Any:
        user = safe_dict(getattr(state, "user", None))
        session = safe_dict(getattr(state, "session", None))
        economy = safe_dict(getattr(state, "economy", None))
        product = safe_dict(getattr(state, "product", None))
        meta = safe_dict(getattr(state, "meta", None))

        timestamp_ms = int(getattr(state, "timestamp_ms", 0) or 0)
        now_s = float(timestamp_ms) / 1000.0 if timestamp_ms > 0 else None
        user_id = str(getattr(state, "user_id", None) or user.get("user_id") or "anonymous")
        sessions_count = int(user.get("sessions") or session.get("sessions") or 0)
        payments = float(user.get("payments") or economy.get("payments") or 0.0)
        last_seen = float(user.get("last_seen") or now_s or 0.0)

        merged_economy = dict(economy)
        merged_meta = dict(meta)
        merged_economy["predicted_ltv"] = self._ltv.predicted_ltv(
            LtvInput(
                user_id=user_id,
                sessions=sessions_count,
                payments=payments,
                last_seen=last_seen,
                now_s=now_s,
            )
        )
        merged_meta["world_model"] = "canonical_decision_world_model@v1"
        merged_meta["world_model_kind"] = self._kind

        semantic_view = getattr(state, "world_model_semantics", None)
        tenant_id = str(getattr(state, "tenant_id", "") or meta.get("tenant_id") or "").strip()
        business_id = str(meta.get("business_id") or product.get("business_id") or "").strip()
        if (
            semantic_view is not None
            and tenant_id
            and business_id
            and (
                semantic_view.tenant_id != tenant_id
                or semantic_view.business_id != business_id
            )
        ):
            raise ValueError("world_model_semantics scope mismatch")
        if self._state_snapshot_store is not None and tenant_id and business_id:
            snapshot = self._state_snapshot_store.load_latest(
                tenant_id=tenant_id,
                business_id=business_id,
            )
            if snapshot is not None:
                if snapshot.tenant_id != tenant_id or snapshot.business_id != business_id:
                    raise ValueError("canonical state snapshot scope mismatch")
                semantic_view = snapshot.semantic_view
                merged_meta["canonical_business_state_id"] = snapshot.state_id

        if self._kind in {"pricing@v1", "hybrid@v1", "hybrid"}:
            merged_economy, merged_meta = enrich_pricing(
                state=state,
                product=product,
                economy=merged_economy,
                meta=merged_meta,
                store=self._store,
            )

        updates = {"economy": merged_economy, "meta": merged_meta}
        if hasattr(state, "world_model_semantics"):
            updates["world_model_semantics"] = semantic_view
        return replace(state, **updates)
