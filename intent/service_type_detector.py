from __future__ import annotations

from contracts.demand import ClientIntentSignal
from intent.keyword_rules import KeywordRule, detect_keyword_value

_SERVICE_RULES = (
    KeywordRule('psychology', ('психолог', 'психотерап', 'therapy', 'therapist')),
    KeywordRule('repair', ('ремонт', 'repair', 'fix')),
    KeywordRule('cleaning', ('уборка', 'cleaning', 'cleaner')),
    KeywordRule('legal', ('юрист', 'lawyer', 'legal')),
)


class ServiceTypeDetector:
    def detect(self, signals: tuple[ClientIntentSignal, ...], text: str = '') -> str:
        for signal in signals:
            if signal.signal_name == 'servicetype':
                return str(signal.signal_value)
        return detect_keyword_value(text=text, rules=_SERVICE_RULES, default='general')
