from __future__ import annotations

from enum import Enum


class SignalFreshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"


class SnapshotStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class SnapshotRejectionReason(str, Enum):
    STALE_SIGNAL = "stale_signal"
    INCOMPLETE_STATE = "incomplete_state"
    INTEGRITY_VIOLATION = "integrity_violation"


class ReaderKind(str, Enum):
    CUSTOMER = "customer"
    REVENUE = "revenue"
    CAMPAIGN = "campaign"
    PRODUCT = "product"
    MESSAGING = "messaging"
    MARKET = "market"
