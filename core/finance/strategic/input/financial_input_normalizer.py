from __future__ import annotations

from core.finance.strategic.decimal_utils import quantize_money, to_decimal


class FinancialInputNormalizer:
    def normalize(self, raw: dict) -> dict:
        data = dict(raw)
        data['tenant_id'] = str(data.get('tenant_id') or '').strip() or 'default'
        data['correlation_id'] = str(data.get('correlation_id') or '').strip() or 'strategic-finance'
        data['period_months'] = int(data.get('period_months') or 12)
        for key in ('revenue', 'costs', 'cash', 'debt'):
            data[key] = quantize_money(to_decimal(data.get(key)))
        for key in ('churn_rate', 'gross_margin_rate', 'growth_rate'):
            data[key] = to_decimal(data.get(key))
        data['customers'] = int(data.get('customers') or 0)
        data['new_customers'] = int(data.get('new_customers') or 0)
        data['channel_spend'] = {
            str(k): quantize_money(to_decimal(v))
            for k, v in dict(data.get('channel_spend') or {}).items()
        }
        data['channel_new_customers'] = {
            str(k): int(v)
            for k, v in dict(data.get('channel_new_customers') or {}).items()
        }
        data['assumptions'] = {
            str(k): to_decimal(v)
            for k, v in dict(data.get('assumptions') or {}).items()
        }
        data['entities'] = tuple(str(x) for x in tuple(data.get('entities') or ()))
        data['metadata'] = dict(data.get('metadata') or {})
        return data
