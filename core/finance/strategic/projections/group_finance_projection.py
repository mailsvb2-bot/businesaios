from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class GroupFinanceProjection:
    def project(self, entity_snapshots: list[dict[str, Decimal]]) -> dict[str, Decimal]:
        return {
            'revenue': q2(sum((item.get('revenue', Decimal('0')) for item in entity_snapshots), start=Decimal('0'))),
            'costs': q2(sum((item.get('costs', Decimal('0')) for item in entity_snapshots), start=Decimal('0'))),
            'cash': q2(sum((item.get('cash', Decimal('0')) for item in entity_snapshots), start=Decimal('0'))),
        }
