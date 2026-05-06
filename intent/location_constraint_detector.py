from __future__ import annotations

from contracts.demand import ClientIntentSignal
from intent.keyword_rules import KeywordRule, detect_keyword_value

_LOCATION_RULES = (
    KeywordRule('remote', ('remote', 'online', 'удаленно', 'онлайн')),
    KeywordRule('local', ('near me', 'рядом', 'поблизости', 'в моем районе')),
)


class LocationConstraintDetector:
    def detect(self, signals: tuple[ClientIntentSignal, ...], text: str = '') -> str:
        for signal in signals:
            if signal.signal_name in {'location', 'geo'}:
                return str(signal.signal_value)
        return detect_keyword_value(text=text, rules=_LOCATION_RULES, default='any')
