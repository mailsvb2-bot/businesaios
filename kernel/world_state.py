from dataclasses import asdict, dataclass, field
from typing import Any

from contracts.world_model_semantics import WorldModelSemanticViewV1
from core.utils.canonical import canonical_json_bytes


@dataclass(frozen=True)
class WorldStateV1:
    """Canonical WorldState.

    Requirements:
    - versioned schema (schema_version)
    - canonicalizable/deterministic serialization
    - includes all fields relevant for decisions (including deployment proposals)
    """

    schema_version: int
    user: dict[str, Any]
    session: dict[str, Any]
    product: dict[str, Any]
    economy: dict[str, Any]
    timestamp_ms: int

    # Tenant isolation (must be propagated everywhere)
    tenant_id: str = "default"
    meta: dict[str, Any] = field(default_factory=dict)

    # Additional canonical fields:
    user_id: str | None = None
    safe_mode: bool = False

    # Economic governance fields (required in strict prod)
    capital: float = 0.0
    horizon_state: str = "stable"

    # Behavioral snapshot (read-model input for DecisionCore; optional)
    behavior: dict[str, Any] | None = None

    # DecisionCore-issued constraints for pricing/offer selection (no second brain)
    # Example: {"max_band": "low"|"standard"|"premium"}
    price_constraints: dict[str, Any] | None = None

    # Self-driving deployment proposal (set by LearningSystem; DecisionCore decides)
    deployment_proposal: dict[str, Any] | None = None

    # Safe human override request (still decided by DecisionCore)
    manual_override: bool = False

    # Canonical semantic view over the same sovereign state; never a second WorldState.
    world_model_semantics: WorldModelSemanticViewV1 | None = None

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(asdict(self))


"""NOTE:

This module intentionally exposes a *single* canonical WorldState.

Do NOT add additional public WorldState variants ("V2", "TelegramWorldState", etc.).
Multiple competing state schemas create a hidden "second brain" via alternative paths.
"""
