from __future__ import annotations

from core.world_model.contracts import FORBIDDEN_DECISION_KEYS
from core.world_model.errors import WorldModelIntegrityError
from core.world_model.types import WorldModelBuildInput


class BuildInputGuard:
    def validate(self, *, build_input: WorldModelBuildInput) -> None:
        if not str(build_input.tenant_id).strip():
            raise WorldModelIntegrityError("world_model missing tenant_id")
        if not str(build_input.business_id).strip():
            raise WorldModelIntegrityError("world_model missing business_id")
        if not str(build_input.customer_id).strip():
            raise WorldModelIntegrityError("world_model missing customer_id")
        if not str(build_input.product_id).strip():
            raise WorldModelIntegrityError("world_model missing product_id")
        if not str(build_input.channel).strip():
            raise WorldModelIntegrityError("world_model missing channel")
        if not str(build_input.geo).strip():
            raise WorldModelIntegrityError("world_model missing geo")
        for key in build_input.context.keys():
            lowered = str(key).strip().lower()
            if lowered in FORBIDDEN_DECISION_KEYS:
                raise WorldModelIntegrityError(f"world_model forbidden decision-like context key={key}")
