from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from contracts.platforms.market_intelligence_advanced_contract import OpportunityEvidence, UnifiedSignal


CANON_MARKET_INTELLIGENCE_ADVANCED_MEMORY_BRIDGE = True


@dataclass
class AdvancedBusinessMemoryBridge:
    def to_memory_payload(self, *, signals: Iterable[UnifiedSignal], opportunities: Iterable[OpportunityEvidence], pattern_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        signal_rows = [item.as_dict() for item in signals]
        opportunity_rows = [item.as_dict() for item in opportunities]
        return {
            'market_intelligence_advanced': {
                'signals': signal_rows[:100],
                'opportunities': opportunity_rows[:50],
                'patterns': dict(pattern_payload or {}),
                'summary': {
                    'signals_count': len(signal_rows),
                    'opportunities_count': len(opportunity_rows),
                },
            }
        }


__all__ = ['CANON_MARKET_INTELLIGENCE_ADVANCED_MEMORY_BRIDGE', 'AdvancedBusinessMemoryBridge']
