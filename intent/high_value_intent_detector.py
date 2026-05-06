from __future__ import annotations

from contracts.demand import ClientIntentSignal
from intent.keyword_rules import KeywordRule, detect_keyword_value

_HIGH_VALUE_RULES = (
    KeywordRule('true', ('premium', 'vip', 'high-end', 'дорого', 'elite')),
)


class HighValueIntentDetector:
    def detect(self, signals: tuple[ClientIntentSignal, ...], text: str = '') -> str:
        for signal in signals:
            if signal.signal_name == 'highvalue':
                return str(signal.signal_value)
        return detect_keyword_value(text=text, rules=_HIGH_VALUE_RULES, default='false')
