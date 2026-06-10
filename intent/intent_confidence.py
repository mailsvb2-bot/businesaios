from __future__ import annotations

from contracts.demand import ClientIntentSignal


def compute_confidence(signals: tuple[ClientIntentSignal, ...]) -> float:
    if not signals:
        return 0.4
    return round(sum(max(0.0, min(1.0, s.confidence)) for s in signals) / len(signals), 4)
