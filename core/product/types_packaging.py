from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.product.enums import PackagingChangeType, ProposalMode, ProposalStatus
from core.product.types_roadmap import PRODUCT_MODULE_ISSUER


@dataclass(frozen=True)
class TierDefinition:
    tier_name: str
    included_features: list[str]
    seat_limit: int | None = None
    usage_limit: int | None = None


@dataclass(frozen=True)
class PackagingChange:
    change_type: PackagingChangeType
    target: str
    from_value: str | None
    to_value: str | None
    rationale: str


@dataclass(frozen=True)
class PackagingProposal:
    proposal_id: str
    product_id: str
    changes: list[PackagingChange]
    tier_structure: list[TierDefinition]
    status: ProposalStatus = ProposalStatus.DRAFT
    issuer_id: str = PRODUCT_MODULE_ISSUER
    mode: ProposalMode = ProposalMode.ADVISORY
    executable: bool = False
