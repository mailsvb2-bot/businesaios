from __future__ import annotations

from core.product.enums import ProposalMode
from core.product.types import GuardVerdict, PRODUCT_MODULE_ISSUER


class ProposalBoundaryGuard:
    def check(self, proposal) -> GuardVerdict:
        if getattr(proposal, "issuer_id", "") != PRODUCT_MODULE_ISSUER:
            return GuardVerdict(False, "invalid_issuer_id", "Proposal issuer_id violates product boundary")
        if getattr(proposal, "mode", None) != ProposalMode.ADVISORY:
            return GuardVerdict(False, "non_advisory_proposal", "Product module may only emit advisory proposals")
        if getattr(proposal, "executable", True):
            return GuardVerdict(False, "executable_proposal_forbidden", "Product module may not emit executable proposals")
        return GuardVerdict(True, "ok", "Proposal respects product advisory-only boundary")
