from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.product.enums import PackagingChangeType, ProposalMode, ProposalStatus
from core.product.types_roadmap import PRODUCT_MODULE_ISSUER


@dataclass(frozen=True)
class TierDefinition:
    tier_name: str
    included_features: list[str]
    seat_limit: Optional[int] = None
    usage_limit: Optional[int] = None


@dataclass(frozen=True)
class PackagingChange:
    change_type: PackagingChangeType
    target: str
    from_value: Optional[str]
    to_value: Optional[str]
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
