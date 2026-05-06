from __future__ import annotations

from contracts.demand import ClientIntentSignal
from intent.keyword_rules import KeywordRule, detect_keyword_value

_URGENCY_RULES = (
    KeywordRule('high', ('urgent', 'asap', 'срочно', 'сегодня', 'today')),
    KeywordRule('medium', ('soon', 'this week', 'на неделе')),
)


class UrgencyDetector:
    def detect(self, signals: tuple[ClientIntentSignal, ...], text: str = '') -> str:
        for signal in signals:
            if signal.signal_name == 'urgency':
                return str(signal.signal_value)
        return detect_keyword_value(text=text, rules=_URGENCY_RULES, default='standard')
