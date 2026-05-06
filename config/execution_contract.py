from __future__ import annotations

CANON_COMPAT_SHIM = True

CANONICAL_DECISION_PATH = "core.decision"
LEGACY_CANONICAL_DECISION_PATH = "core.ai.decision_core"
CANONICAL_DECISION_PATH_ALIASES = (
    CANONICAL_DECISION_PATH,
    LEGACY_CANONICAL_DECISION_PATH,
)
CANONICAL_OPTIMIZATION_TARGET = "route_quality_and_business_value"
DEFAULT_DELIVERY_CHANNEL = "crm"
DEFAULT_MANUAL_REVIEW_CHANNEL = "manual_review"
DELIVERY_ALLOWED_CHANNELS = (
    "crm",
    "email",
    "sms",
    "telegram",
    "whatsapp",
    "call_center",
    "internal_marketplace",
)
STUB_DELIVERY_DETAIL = "adapter_stub_dispatched"

STUB_DELIVERY_STATUS = "accepted"
STUB_DELIVERY_PUBLIC_DETAIL = "transport_not_configured"


def is_canonical_decision_path(value: object) -> bool:
    normalized = str(value or "").strip()
    return normalized in CANONICAL_DECISION_PATH_ALIASES
