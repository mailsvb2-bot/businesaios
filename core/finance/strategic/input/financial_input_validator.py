from __future__ import annotations

from decimal import Decimal


class FinancialInputValidator:
    def validate(self, data: dict) -> None:
        if not data.get('tenant_id'):
            raise ValueError('tenant_id is required')
        if not data.get('correlation_id'):
            raise ValueError('correlation_id is required')
        if int(data.get('period_months') or 0) <= 0:
            raise ValueError('period_months must be > 0')
        for key in ('revenue', 'costs', 'cash', 'debt'):
            if data.get(key) is None:
                raise ValueError(f'{key} is required')
        if data['revenue'] < Decimal('0') or data['costs'] < Decimal('0') or data['cash'] < Decimal('0'):
            raise ValueError('money fields must be non-negative')
        if data['customers'] < 0 or data['new_customers'] < 0:
            raise ValueError('customer counts must be non-negative')
