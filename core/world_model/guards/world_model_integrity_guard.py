from __future__ import annotations

from core.world_model.contracts import (
    WORLD_SNAPSHOT_DECISION_ISSUER,
    WORLD_SNAPSHOT_READ_ONLY,
    WORLD_SNAPSHOT_ROLE,
    WORLD_SNAPSHOT_SCHEMA_VERSION,
)
from core.world_model.errors import WorldModelIntegrityError
from core.world_model.types import BusinessState, WorldSnapshot


class WorldModelIntegrityGuard:
    def validate_business_state(self, *, business_state: BusinessState) -> None:
        if not str(business_state.tenant_id).strip():
            raise WorldModelIntegrityError("world_model missing tenant_id")
        if not str(business_state.business_id).strip():
            raise WorldModelIntegrityError("world_model missing business_id")
        if business_state.customer.customer_id in {"", "unknown"}:
            raise WorldModelIntegrityError("world_model invalid customer_id")
        if business_state.product.product_id in {"", "unknown"}:
            raise WorldModelIntegrityError("world_model invalid product_id")

    def validate_snapshot(self, *, snapshot: WorldSnapshot) -> None:
        if snapshot.schema_version != WORLD_SNAPSHOT_SCHEMA_VERSION:
            raise WorldModelIntegrityError(f"world_model schema mismatch schema_version={snapshot.schema_version}")
        if snapshot.snapshot_id.strip() == "":
            raise WorldModelIntegrityError("world_model empty snapshot_id")
        contract = snapshot.explain.get("contract") or {}
        if contract.get("read_only") is not WORLD_SNAPSHOT_READ_ONLY:
            raise WorldModelIntegrityError("world_model explain contract read_only mismatch")
        if contract.get("decision_issuer") != WORLD_SNAPSHOT_DECISION_ISSUER:
            raise WorldModelIntegrityError("world_model explain contract decision_issuer mismatch")
        if contract.get("role") != WORLD_SNAPSHOT_ROLE:
            raise WorldModelIntegrityError("world_model explain contract role mismatch")
        metadata_contract = snapshot.metadata.get("contract") or {}
        if metadata_contract.get("read_only") is not WORLD_SNAPSHOT_READ_ONLY:
            raise WorldModelIntegrityError("world_model metadata contract read_only mismatch")
