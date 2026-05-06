from __future__ import annotations

from decimal import Decimal


class ForecastDeltaExplainer:
    def explain(self, previous: Decimal, current: Decimal) -> str:
        return f'Forecast changed by {current - previous} from {previous} to {current}.'
