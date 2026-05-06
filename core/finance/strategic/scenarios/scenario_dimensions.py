from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from core.finance.strategic.decimal_utils import to_decimal
from core.finance.strategic.types import FinancialInput, Scenario


@dataclass(frozen=True)
class EnterpriseScenarioView:
    channels: dict[str, Decimal]
    segments: dict[str, Decimal]
    products: dict[str, Decimal]
    entities: dict[str, Decimal]
    receivable_days: Decimal
    payable_days: Decimal
    inventory_days: Decimal


class EnterpriseScenarioInputs:
    def from_financial_input(self, finance_input: FinancialInput) -> EnterpriseScenarioView:
        metadata = dict(finance_input.metadata or {})
        return EnterpriseScenarioView(
            channels={str(k): to_decimal(v) for k, v in dict(metadata.get('channel_mix') or {}).items()},
            segments={str(k): to_decimal(v) for k, v in dict(metadata.get('segment_mix') or {}).items()},
            products={str(k): to_decimal(v) for k, v in dict(metadata.get('product_mix') or {}).items()},
            entities={str(k): to_decimal(v) for k, v in dict(metadata.get('entity_mix') or {}).items()},
            receivable_days=to_decimal(metadata.get('receivable_days') or 0),
            payable_days=to_decimal(metadata.get('payable_days') or 0),
            inventory_days=to_decimal(metadata.get('inventory_days') or 0),
        )

    def bias_signal(self, finance_input: FinancialInput, scenario: Scenario) -> Decimal:
        view = self.from_financial_input(finance_input)
        total = Decimal('0')
        for group, bias in ((view.channels, scenario.channel_bias), (view.segments, scenario.segment_bias), (view.products, scenario.product_bias), (view.entities, scenario.entity_bias)):
            if not group:
                continue
            subtotal = sum((weight * bias.get(name, Decimal('1'))) for name, weight in group.items())
            total += subtotal / Decimal(str(len(group) or 1))
        return total
