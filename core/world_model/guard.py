from __future__ import annotations

from core.world_model.contracts import FORBIDDEN_DECISION_KEYS
from core.world_model.errors import WorldModelIntegrityError
from core.world_model.guards.build_input_guard import BuildInputGuard
from core.world_model.guards.incomplete_state_guard import IncompleteStateGuard
from core.world_model.guards.stale_signal_guard import StaleSignalGuard
from core.world_model.guards.world_model_integrity_guard import WorldModelIntegrityGuard
from core.world_model.types import (
    BusinessState,
    CompletenessReport,
    FreshnessReport,
    WorldModelBuildInput,
    WorldSnapshot,
)


class DecisionSurfaceGuard:
    def validate_mapping(self, *, mapping: dict, surface_name: str) -> None:
        for key in mapping:
            lowered = str(key).strip().lower()
            if lowered in FORBIDDEN_DECISION_KEYS:
                raise WorldModelIntegrityError(
                    f"world_model forbidden decision-like key={key} surface={surface_name}"
                )


class WorldModelGuard:
    def __init__(
        self,
        *,
        build_input_guard: BuildInputGuard | None = None,
        stale_signal_guard: StaleSignalGuard | None = None,
        incomplete_state_guard: IncompleteStateGuard | None = None,
        integrity_guard: WorldModelIntegrityGuard | None = None,
        decision_surface_guard: DecisionSurfaceGuard | None = None,
    ) -> None:
        self._build_input_guard = build_input_guard or BuildInputGuard()
        self._stale_signal_guard = stale_signal_guard or StaleSignalGuard()
        self._incomplete_state_guard = incomplete_state_guard or IncompleteStateGuard()
        self._integrity_guard = integrity_guard or WorldModelIntegrityGuard()
        self._decision_surface_guard = decision_surface_guard or DecisionSurfaceGuard()

    def validate_build_input(self, *, build_input: WorldModelBuildInput) -> None:
        self._build_input_guard.validate(build_input=build_input)

    def validate_pre_snapshot(self, *, business_state: BusinessState, freshness: FreshnessReport, completeness: CompletenessReport) -> None:
        self._integrity_guard.validate_business_state(business_state=business_state)
        self._stale_signal_guard.validate(freshness=freshness)
        self._incomplete_state_guard.validate(completeness=completeness)
        self._decision_surface_guard.validate_mapping(mapping=business_state.messaging, surface_name="business_state.messaging")
        self._decision_surface_guard.validate_mapping(mapping=business_state.economics, surface_name="business_state.economics")

    def validate_snapshot(self, *, snapshot: WorldSnapshot) -> None:
        self._decision_surface_guard.validate_mapping(mapping=snapshot.explain, surface_name="snapshot.explain")
        self._decision_surface_guard.validate_mapping(mapping=snapshot.metadata, surface_name="snapshot.metadata")
        self._integrity_guard.validate_snapshot(snapshot=snapshot)


def require_world_confidence(snapshot: WorldSnapshot, minimum: float = 0.1) -> None:
    if snapshot.confidence < minimum:
        from core.world_model.errors import WorldModelGuardViolation
        raise WorldModelGuardViolation(f"World snapshot confidence {snapshot.confidence} is below {minimum}.")
