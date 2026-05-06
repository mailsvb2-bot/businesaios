from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


CANON_STRATEGY_HINT_CONTRACT = True


@dataclass(frozen=True)
class StrategyHint:
    hint_key: str
    confidence: float = 0.0
    reason: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'hint_key': str(self.hint_key),
            'confidence': float(self.confidence),
            'reason': str(self.reason),
            'metadata': dict(self.metadata),
        }


__all__ = ['CANON_STRATEGY_HINT_CONTRACT', 'StrategyHint']
