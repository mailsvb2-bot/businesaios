from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.allocation.allocation_constraints import AllocationConstraints
from core.finance.strategic.decimal_utils import q2


class ChannelAllocator:
    def allocate(
        self,
        total_budget: Decimal,
        channel_scores: dict[str, Decimal],
        constraints: AllocationConstraints,
    ) -> dict[str, Decimal]:
        if not channel_scores:
            return {}
        total_score = sum(channel_scores.values(), start=Decimal('0'))
        if total_score <= Decimal('0'):
            equal = q2(total_budget / Decimal(str(len(channel_scores))))
            result = {key: equal for key in channel_scores}
        else:
            result = {
                key: q2(total_budget * score / total_score)
                for key, score in channel_scores.items()
            }
        max_per_channel = q2(total_budget * constraints.max_channel_share)
        result = {key: min(value, max_per_channel) for key, value in result.items()}
        allocated = sum(result.values(), start=Decimal('0'))
        remainder = q2(total_budget - allocated)
        if remainder > Decimal('0'):
            best_key = max(channel_scores, key=channel_scores.get)
            result[best_key] = q2(result.get(best_key, Decimal('0')) + remainder)
        return {key: q2(value) for key, value in result.items()}
