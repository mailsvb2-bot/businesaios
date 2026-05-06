from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class IntercompanyEliminator:
    def eliminate(
        self,
        consolidated: dict[str, Decimal],
        intercompany_revenue: Decimal = Decimal('0'),
        intercompany_costs: Decimal = Decimal('0'),
    ) -> dict[str, Decimal]:
        return {
            'revenue': q2(consolidated.get('revenue', Decimal('0')) - intercompany_revenue),
            'costs': q2(consolidated.get('costs', Decimal('0')) - intercompany_costs),
            'cash': q2(consolidated.get('cash', Decimal('0'))),
        }
