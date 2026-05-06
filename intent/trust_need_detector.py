from __future__ import annotations

from contracts.demand import ClientIntentSignal
from intent.keyword_rules import KeywordRule, detect_keyword_value

_TRUST_RULES = (
    KeywordRule('high', ('отзывы', 'review', 'verified', 'гарантия', 'guarantee', 'trust')),
)


class TrustNeedDetector:
    def detect(self, signals: tuple[ClientIntentSignal, ...], text: str = '') -> str:
        for signal in signals:
            if signal.signal_name == 'trust':
                return str(signal.signal_value)
        return detect_keyword_value(text=text, rules=_TRUST_RULES, default='normal')
