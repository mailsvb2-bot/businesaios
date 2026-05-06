from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryStatePolicy:
    """Canonical operational defaults for delivery-state persistence.

    This is an infrastructure contract, not decision logic. It centralizes
    phase names and pagination / threshold normalization so delivery-state code
    does not carry duplicated literals that can drift over time.
    """

    finalized_phase: str = "finalized"
    accepted_phase: str = "accepted_for_delivery"
    recovery_phase: str = "accepted_recovery_requeued"
    default_list_limit: int = 100
    min_list_limit: int = 1
    min_stale_threshold_ms: int = 0

    def normalize_limit(self, value: int) -> int:
        return max(self.min_list_limit, int(value))

    def normalize_stale_threshold_ms(self, value: int) -> int:
        return max(self.min_stale_threshold_ms, int(value))


DEFAULT_DELIVERY_STATE_POLICY = DeliveryStatePolicy()


__all__ = ["DEFAULT_DELIVERY_STATE_POLICY", "DeliveryStatePolicy"]
