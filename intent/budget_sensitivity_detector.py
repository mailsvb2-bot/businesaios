from __future__ import annotations

from contracts.demand import ClientIntentSignal
from intent.keyword_rules import KeywordRule, detect_keyword_value

_BUDGET_RULES = (
    KeywordRule('sensitive', ('дешево', 'подешевле', 'недорого', 'price', 'cheap', 'budget')),
    KeywordRule('premium', ('premium', 'vip', 'дорого', 'лучший', 'best')),
)


class BudgetSensitivityDetector:
    def detect(self, signals: tuple[ClientIntentSignal, ...], text: str = '') -> str:
        for signal in signals:
            if signal.signal_name == 'budget':
                return str(signal.signal_value)
        return detect_keyword_value(text=text, rules=_BUDGET_RULES, default='mid')
