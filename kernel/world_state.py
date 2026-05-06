from dataclasses import dataclass, asdict, field
from typing import Any, Dict, Optional

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
    user: Dict[str, Any]
    session: Dict[str, Any]
    product: Dict[str, Any]
    economy: Dict[str, Any]
    timestamp_ms: int

    # Tenant isolation (must be propagated everywhere)
    tenant_id: str = "default"
    meta: Dict[str, Any] = field(default_factory=dict)

    # Additional canonical fields:
    user_id: Optional[str] = None
    safe_mode: bool = False

    # Economic governance fields (required in strict prod)
    capital: float = 0.0
    horizon_state: str = "stable"

    # Behavioral snapshot (read-model input for DecisionCore; optional)
    behavior: Optional[Dict[str, Any]] = None

    # DecisionCore-issued constraints for pricing/offer selection (no second brain)
    # Example: {"max_band": "low"|"standard"|"premium"}
    price_constraints: Optional[Dict[str, Any]] = None

    # Self-driving deployment proposal (set by LearningSystem; DecisionCore decides)
    deployment_proposal: Optional[Dict[str, Any]] = None

    # Safe human override request (still decided by DecisionCore)
    manual_override: bool = False

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(asdict(self))


"""NOTE:

This module intentionally exposes a *single* canonical WorldState.

Do NOT add additional public WorldState variants ("V2", "TelegramWorldState", etc.).
Multiple competing state schemas create a hidden "second brain" via alternative paths.
"""