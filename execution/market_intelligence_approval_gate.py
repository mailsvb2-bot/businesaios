from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from collections.abc import Mapping


CANON_MARKET_INTELLIGENCE_APPROVAL_GATE = True


@dataclass(frozen=True)
class MarketIntelligenceApprovalGate:
    approval_resolver: Callable[[str, Mapping[str, object]], bool] | None = None

    def ensure_allowed(self, *, tenant_id: str, risk: Mapping[str, object]) -> None:
        if not bool(risk.get('requires_approval')):
            return
        if self.approval_resolver is None:
            raise ValueError('approval required but no approval_resolver configured')
        if not bool(self.approval_resolver(str(tenant_id), risk)):
            raise ValueError('approval denied for market intelligence request')


__all__ = ['CANON_MARKET_INTELLIGENCE_APPROVAL_GATE', 'MarketIntelligenceApprovalGate']
