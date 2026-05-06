from __future__ import annotations

from contracts.demand import ClientIntentSignal
from intent.keyword_rules import KeywordRule, detect_keyword_value

_REPEAT_RULES = (
    KeywordRule('true', ('again', 'повторно', 'ещё раз', 'снова')),
)


class RepeatPurchaseDetector:
    def detect(self, signals: tuple[ClientIntentSignal, ...], text: str = '') -> str:
        for signal in signals:
            if signal.signal_name == 'repeat':
                return str(signal.signal_value)
        return detect_keyword_value(text=text, rules=_REPEAT_RULES, default='false')
