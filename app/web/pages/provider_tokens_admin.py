from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload


CANON_WEB_PROVIDER_TOKENS_ADMIN_PAGE = True


@dataclass(frozen=True, slots=True)
class ProviderTokensAdminPage:
    kind: str = 'provider_tokens_admin_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        business_id = str(normalized.get('business_id') or '').strip() or 'default-business'
        rows = tuple(dict(item) for item in tuple(normalized.get('rows', ()) or ()))
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'business_id': business_id,
                'title': 'Provider / Token Admin',
                'subtitle': 'Индивидуальная админка для токенов и business connectors. Roadmap/contract-only каналы не показываются как готовые подключения.',
                'rows': rows,
                'actions': {
                    'list_endpoint': '/control-plane/provider-admin/catalog',
                    'capabilities_endpoint': '/control-plane/provider-admin/capabilities',
                    'truth_matrix_path': '/web/provider-truth',
                    'truth_matrix_endpoint': '/control-plane/provider-admin/catalog',
                    'activate_endpoint': '/control-plane/provider-admin/activate',
                    'platform_admin_path': '/web/platform-admin',
                },
                'truth_rules': {
                    'provider_in_catalog_is_not_implemented': True,
                    'endpoint_is_not_live_ready': True,
                    'runtime_write_operation_is_not_write_supported': True,
                    'telegram_bot_is_not_telegram_ads': True,
                    'write_requires_approval_budget_risk_verification_evidence': True,
                },
                'ui_schema': {
                    'primary_buttons': [
                        {'label': 'Открыть Provider Truth Matrix', 'provider_key': '*', 'action': 'open_truth_matrix'},
                        {'label': 'Ввести токен для Telegram Bot', 'provider_key': 'telegram_bot', 'action': 'open_modal'},
                        {'label': 'Ввести токен для сайта', 'provider_key': 'generic_website', 'action': 'open_modal'},
                        {'label': 'Ввести токен для Shopify', 'provider_key': 'shopify', 'action': 'open_modal'},
                        {'label': 'Ввести токен для HubSpot', 'provider_key': 'hubspot', 'action': 'open_modal'},
                        {'label': 'Ввести токен для Google Ads (read-only)', 'provider_key': 'google_ads', 'action': 'open_modal'},
                        {'label': 'Meta Ads: только контракт, не подключать как готовое', 'provider_key': 'meta_ads', 'action': 'open_capability_evidence', 'disabled': True},
                    ],
                    'modal_behavior': {
                        'submit_label': 'Принять и подключить',
                        'success_toast': 'Данные приняты. Подключение и onboarding запущены.',
                        'post_submit_refresh': True,
                    },
                },
                'tenant_bound': True,
            },
        )


__all__ = ['CANON_WEB_PROVIDER_TOKENS_ADMIN_PAGE', 'ProviderTokensAdminPage']
