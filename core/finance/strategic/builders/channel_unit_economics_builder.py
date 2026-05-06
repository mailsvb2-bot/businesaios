from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class ChannelUnitEconomicsBuilder:
    def build(self, segmented_cac: dict[str, Decimal], ltv: Decimal) -> dict[str, dict[str, Decimal]]:
        result: dict[str, dict[str, Decimal]] = {}
        for channel, cac in segmented_cac.items():
            result[channel] = {
                'cac': q2(cac),
                'ltv': q2(ltv),
                'ltv_to_cac': q2((ltv / cac) if cac else Decimal('0')),
            }
        return result
