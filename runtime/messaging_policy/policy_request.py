from __future__ import annotations

from dataclasses import dataclass

from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging.channel_preference import ChannelPreference
from runtime.messaging_policy.delivery_snapshot import DeliverySnapshot
from runtime.messaging_policy.discipline import MessagingPolicyDisciplineViolation
from runtime.messaging_policy.unanswered_snapshot import UnansweredSnapshot

_CONTACT_BASES = frozenset({"inbound", "explicit_consent", "existing_customer", "requested_followup", "none"})


def _normalize_optional(value: str | None) -> str | None:
    text = str(value or "").strip()
    return normalize_channel(text) if text else None


def _normalize_many(value) -> tuple[str, ...]:
    if not isinstance(value, list | tuple | set):
        return ()
    out = [normalize_channel(str(item).strip()) for item in value if str(item or "").strip()]
    return tuple(dict.fromkeys(out))


def _normalize_contact_basis(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise MessagingPolicyDisciplineViolation("contact_basis must be a string when provided")
    text = value.strip().lower()
    if not text or text not in _CONTACT_BASES:
        raise MessagingPolicyDisciplineViolation(f"unsupported contact_basis:{text}")
    return text


@dataclass(frozen=True)
class PolicyRequest:
    preference: ChannelPreference
    preferred_channel: str | None = None
    fallback_channels: tuple[str, ...] = ()
    verified_only: bool = False
    critical: bool = True
    attempt_index: int = 0
    unanswered_threshold_s: int = 0
    delivery_snapshot: DeliverySnapshot = DeliverySnapshot()
    unanswered_snapshot: UnansweredSnapshot = UnansweredSnapshot()
    contact_basis: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "preferred_channel", _normalize_optional(self.preferred_channel))
        object.__setattr__(self, "fallback_channels", _normalize_many(self.fallback_channels))
        object.__setattr__(self, "verified_only", bool(self.verified_only))
        object.__setattr__(self, "critical", bool(self.critical))
        object.__setattr__(self, "attempt_index", max(0, int(self.attempt_index or 0)))
        object.__setattr__(self, "unanswered_threshold_s", max(0, int(self.unanswered_threshold_s or 0)))
        object.__setattr__(self, "contact_basis", _normalize_contact_basis(self.contact_basis))
