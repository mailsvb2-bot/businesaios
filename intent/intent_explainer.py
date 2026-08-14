from __future__ import annotations

from contracts.demand import ClientIntentSignal


class IntentExplainer:
    def explain(self, signals: tuple[ClientIntentSignal, ...]) -> tuple[str, ...]:
        return tuple(f"{s.signal_name}={s.signal_value}@{s.confidence:.2f}" for s in signals)
