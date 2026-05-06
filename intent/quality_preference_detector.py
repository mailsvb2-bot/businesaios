from __future__ import annotations

from contracts.demand import ClientIntentSignal
from intent.keyword_rules import KeywordRule, detect_keyword_value

_QUALITY_RULES = (
    KeywordRule('high', ('качественно', 'лучший', 'premium', 'vip', 'top quality')),
    KeywordRule('basic', ('обычно', 'standard', 'basic')),
)


class QualityPreferenceDetector:
    def detect(self, signals: tuple[ClientIntentSignal, ...], text: str = '') -> str:
        for signal in signals:
            if signal.signal_name == 'quality':
                return str(signal.signal_value)
        return detect_keyword_value(text=text, rules=_QUALITY_RULES, default='standard')
