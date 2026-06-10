from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from app.web.components import PolicyOverrideCard, QuotaUsageCard, TenantSelector
from core.tenancy.normalization import normalize_tenant_id, require_tenant_id
from shared.kinded_payloads import build_kinded_payload
from tenancy.tenant_policy_store import TenantPolicyBundle

CANON_WEB_TENANTS_PAGE = True


def _enum_value(value: Any) -> str:
    return str(getattr(value, 'value', value) or '').strip()


def _bundle_dict(policy_bundle: TenantPolicyBundle | None) -> dict[str, Any]:
    if policy_bundle is None:
        return {}
    return {
        'feature_flags': dict(getattr(getattr(policy_bundle, 'feature_flags', None), '__dict__', {}) or {}),
        'runtime_limits': dict(getattr(getattr(policy_bundle, 'runtime_limits', None), '__dict__', {}) or {}),
        'quotas': dict(getattr(policy_bundle, 'quotas', {}) or {}),
    }


def _tenant_details(record: Any, policy_bundle: TenantPolicyBundle | None) -> dict[str, Any]:
    bundle = _bundle_dict(policy_bundle)
    return {
        'tenant_id': str(getattr(record, 'tenant_id', '') or '').strip(),
        'display_name': str(getattr(record, 'display_name', '') or getattr(record, 'tenant_id', '')).strip(),
        'status': _enum_value(getattr(record, 'status', '')),
        'plan': _enum_value(getattr(record, 'plan', '')),
        'billing_account_id': str(getattr(record, 'billing_account_id', '') or '').strip() or None,
        'data_region': str(getattr(record, 'data_region', '') or '').strip() or None,
        'aliases': tuple(sorted(str(item).strip() for item in tuple(getattr(record, 'aliases', ()) or ()) if str(item).strip())),
        'policy_bundle_present': policy_bundle is not None,
        'feature_flags': bundle.get('feature_flags', {}),
        'runtime_limits': bundle.get('runtime_limits', {}),
        'quotas': bundle.get('quotas', {}),
    }


@dataclass(frozen=True, slots=True)
class TenantsPage:
    tenant_selector: TenantSelector = field(default_factory=TenantSelector)
    policy_override_card: PolicyOverrideCard = field(default_factory=PolicyOverrideCard)
    quota_usage_card: QuotaUsageCard = field(default_factory=QuotaUsageCard)
    kind: str = 'tenants_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        tenant_details = dict(normalized.get('tenant_details', {}) or {})
        details_tenant_id = normalize_tenant_id(tenant_details.get('tenant_id'))
        if details_tenant_id and details_tenant_id != tenant_id:
            tenant_details = {}
        if tenant_details:
            tenant_details['tenant_id'] = tenant_id
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'title': 'Tenants',
                'tenant_selector': normalized.get('tenant_selector'),
                'tenant_details': tenant_details,
                'policy_override': normalized.get('policy_override'),
                'quota_usage': normalized.get('quota_usage'),
                'tenant_bound': True,
            },
        )

    def build_tenant_view(
        self,
        *,
        tenant_id: str,
        tenant_records: Iterable[Any],
        selected_record: Any,
        policy_bundle: TenantPolicyBundle | None,
        override: Any | None,
        quota_usage: Mapping[str, Any],
    ) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        quota_limits = dict(getattr(policy_bundle, 'quotas', {}) or {}) if policy_bundle is not None else {}
        return self.build(
            {
                'tenant_id': required_tenant_id,
                'tenant_selector': self.tenant_selector.build_from_registry(selected_tenant_id=required_tenant_id, tenant_records=tenant_records),
                'tenant_details': _tenant_details(selected_record, policy_bundle),
                'policy_override': self.policy_override_card.build_from_override(tenant_id=required_tenant_id, override=override),
                'quota_usage': self.quota_usage_card.build_from_snapshot(tenant_id=required_tenant_id, usage=quota_usage, limits=quota_limits),
            }
        )


__all__ = ['TenantsPage', 'CANON_WEB_TENANTS_PAGE']
