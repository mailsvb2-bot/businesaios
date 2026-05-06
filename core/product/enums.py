from __future__ import annotations

from enum import Enum


class FeatureStatus(str, Enum):
    DISCOVERY = "discovery"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    RELEASED = "released"
    DEPRECATED = "deprecated"


class FeatureType(str, Enum):
    ACQUISITION = "acquisition"
    ACTIVATION = "activation"
    RETENTION = "retention"
    REVENUE = "revenue"
    EXPERIENCE = "experience"
    PLATFORM = "platform"


class RoadmapBucket(str, Enum):
    NOW = "now"
    NEXT = "next"
    LATER = "later"
    HOLD = "hold"


class PackagingChangeType(str, Enum):
    PRICE = "price"
    LIMIT = "limit"
    BUNDLE = "bundle"
    TIER = "tier"
    ENTITLEMENT = "entitlement"


class ProposalStatus(str, Enum):
    DRAFT = "draft"
    BLOCKED = "blocked"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ProposalMode(str, Enum):
    ADVISORY = "advisory"
