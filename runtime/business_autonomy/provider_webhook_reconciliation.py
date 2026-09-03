from __future__ import annotations

import json
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from runtime.business_autonomy.provider_transport_bindings import ProviderTransportBindings
from runtime.business_autonomy.provider_webhook_route_registry import ProviderWebhookRouteRegistry
from runtime.handler_loader import import_internal_attr
from runtime.platform.config.env_flags import env_str
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import SecretVault

CANON_PROVIDER_WEBHOOK_RECONCILIATION = True
_RECONCILED_PROVIDER_KEYS = frozenset({'telegram_bot', 'vk_messaging', 'max_messaging'})


def _sync_request(**kwargs: Any) -> Any:
    return import_internal_attr('runtime._internal.http_transport', 'sync_request')(**kwargs)


def _form_body(data: Mapping[str, Any]) -> bytes:
    return import_internal_attr('runtime._internal.http_transport', 'form_urlencode')(dict(data))


def _quote_segment(value: object) -> str:
    return import_internal_attr('runtime._internal.http_transport', 'quote_path_segment')(value)


def _json_body(result: Any) -> Any:
    if result is None:
        return {}
    if getattr(result, 'json', None) is not None:
        value = result.json
        return dict(value) if isinstance(value, Mapping) else value
    text = str(getattr(result, 'text', '') or '').strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else parsed


def _require_http_success(result: Any, *, operation: str) -> Any:
    status = int(getattr(result, 'status', 0) or 0)
    if not 200 <= status < 300 or getattr(result, 'error_kind', None):
        raise RuntimeError(f'{operation}:http_{status or 599}')
    return _json_body(result)


@dataclass(frozen=True)
class ProviderWebhookReconciliationResult:
    status: str
    ready: bool
    callback_url: str | None
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class ProviderWebhookReconciler:
    secret_vault: SecretVault

    def reconcile(
        self,
        *,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
    ) -> ProviderWebhookReconciliationResult:
        if provider.provider_key not in _RECONCILED_PROVIDER_KEYS:
            return ProviderWebhookReconciliationResult(
                status='not_applicable', ready=True, callback_url=None, metadata={}
            )
        callback_url = self._callback_url(provider, tenant_id=tenant_id, business_id=business_id)
        if callback_url is None:
            return ProviderWebhookReconciliationResult(
                status='manual_required',
                ready=False,
                callback_url=None,
                metadata={'reason': 'public_base_url_not_configured'},
            )
        if provider.provider_key == 'telegram_bot':
            metadata = self._reconcile_telegram(provider, tenant_id, business_id, callback_url)
        elif provider.provider_key == 'vk_messaging':
            metadata = self._reconcile_vk(provider, tenant_id, business_id, callback_url)
        else:
            metadata = self._reconcile_max(provider, tenant_id, business_id, callback_url)
        return ProviderWebhookReconciliationResult(
            status='reconciled', ready=True, callback_url=callback_url, metadata=metadata
        )

    def _callback_url(
        self,
        provider: ProviderDefinition,
        *,
        tenant_id: str,
        business_id: str,
    ) -> str | None:
        base = env_str('PUBLIC_BASE_URL', '').strip().rstrip('/')
        if not base:
            return None
        if not base.startswith('https://'):
            raise ValueError('PUBLIC_BASE_URL must use HTTPS for provider webhooks')
        path = ProviderWebhookRouteRegistry().describe(provider)['path_template']
        rendered = str(path).format(
            tenant_id=_quote_segment(tenant_id),
            business_id=_quote_segment(business_id),
        )
        return base + rendered

    def _secret(self, provider: ProviderDefinition, tenant_id: str, business_id: str, name: str) -> str:
        ref = SecretRef(
            tenant_id=str(tenant_id),
            connector_id=provider.connector_id,
            scope=str(business_id),
            secret_name=f'{provider.connector_id}.{name}',
        )
        try:
            return self.secret_vault.get(ref).decode('utf-8').strip()
        except Exception:
            return ''

    def _store_secret(
        self,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
        name: str,
        value: str,
    ) -> str:
        ref = SecretRef(
            tenant_id=str(tenant_id),
            connector_id=provider.connector_id,
            scope=str(business_id),
            secret_name=f'{provider.connector_id}.{name}',
        )
        self.secret_vault.put(
            SecretRecord(
                ref=ref,
                ciphertext=b'pending',
                source=SecretSource.CONNECTOR,
                metadata={
                    'provider_key': provider.provider_key,
                    'field_key': name,
                    'business_id': str(business_id),
                    'derived_by': 'provider_webhook_reconciliation',
                },
            ),
            plaintext=str(value).encode('utf-8'),
        )
        return ref.secret_name

    @staticmethod
    def _json_request(*, method: str, url: str, headers: Mapping[str, str], payload: Mapping[str, Any] | None = None) -> Any:
        raw = None if payload is None else json.dumps(dict(payload), separators=(',', ':')).encode('utf-8')
        request_headers = {str(k): str(v) for k, v in dict(headers).items()}
        if raw is not None:
            request_headers.setdefault('Content-Type', 'application/json')
        result = _sync_request(
            method=method,
            url=url,
            headers=request_headers,
            body=raw,
            timeout_s=20,
        )
        return _require_http_success(result, operation='provider_webhook_reconcile')

    @staticmethod
    def _form_request(*, url: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        result = _sync_request(
            method='POST',
            url=url,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            body=_form_body(payload),
            timeout_s=20,
        )
        return _require_http_success(result, operation='provider_webhook_reconcile')

    @staticmethod
    def _provider_base_url(provider: ProviderDefinition) -> str:
        base = str(ProviderTransportBindings().describe(provider).get('base_url') or '').strip().rstrip('/')
        if not base.startswith('https://'):
            raise RuntimeError('provider_https_base_url_missing')
        return base

    def _reconcile_telegram(
        self,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
        callback_url: str,
    ) -> dict[str, Any]:
        bot_token = self._secret(provider, tenant_id, business_id, 'bot_token')
        webhook_secret = self._secret(provider, tenant_id, business_id, 'webhook_secret')
        if not bot_token:
            raise RuntimeError('telegram_bot_token_missing')
        derived_secret_names: tuple[str, ...] = ()
        if not webhook_secret:
            webhook_secret = secrets.token_urlsafe(32)
            derived_secret_names = (
                self._store_secret(provider, tenant_id, business_id, 'webhook_secret', webhook_secret),
            )
        base = self._provider_base_url(provider)
        configured = self._json_request(
            method='POST',
            url=f'{base}/bot{bot_token}/setWebhook',
            headers={},
            payload={
                'url': callback_url,
                'secret_token': webhook_secret,
                'drop_pending_updates': False,
                'allowed_updates': ['message', 'callback_query'],
            },
        )
        if not isinstance(configured, Mapping) or configured.get('ok') is not True:
            raise RuntimeError('telegram_set_webhook_rejected')
        verified = self._json_request(
            method='GET', url=f'{base}/bot{bot_token}/getWebhookInfo', headers={}
        )
        result = verified.get('result') if isinstance(verified.get('result'), Mapping) else {}
        if verified.get('ok') is not True or str(result.get('url') or '').rstrip('/') != callback_url.rstrip('/'):
            raise RuntimeError('telegram_webhook_verification_failed')
        return {
            'provider_state_verified': True,
            'event_types': ('message', 'callback_query'),
            'pending_update_count': int(result.get('pending_update_count') or 0),
            'derived_secret_names': derived_secret_names,
        }

    def _vk_method(
        self,
        provider: ProviderDefinition,
        access_token: str,
        method: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = self._form_request(
            url=f'{self._provider_base_url(provider)}/{method}',
            payload={**dict(payload), 'access_token': access_token, 'v': '5.199'},
        )
        if isinstance(data.get('error'), Mapping):
            error = dict(data['error'])
            raise RuntimeError(f"vk_webhook_reconcile:{error.get('error_code') or 'provider_error'}")
        return data

    def _reconcile_vk(
        self,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
        callback_url: str,
    ) -> dict[str, Any]:
        access_token = self._secret(provider, tenant_id, business_id, 'access_token')
        group_id = self._secret(provider, tenant_id, business_id, 'group_id')
        webhook_secret = self._secret(provider, tenant_id, business_id, 'webhook_secret')
        if not access_token or not group_id.isdigit() or int(group_id) <= 0 or not webhook_secret:
            raise RuntimeError('vk_webhook_credentials_missing')
        confirmation = self._vk_method(
            provider, access_token, 'groups.getCallbackConfirmationCode', {'group_id': int(group_id)}
        )
        response = confirmation.get('response') if isinstance(confirmation.get('response'), Mapping) else {}
        confirmation_code = str(response.get('code') or '').strip()
        if not confirmation_code:
            raise RuntimeError('vk_confirmation_code_missing')
        derived_secret_name = self._store_secret(
            provider, tenant_id, business_id, 'confirmation_code', confirmation_code
        )
        servers = self._vk_method(
            provider, access_token, 'groups.getCallbackServers', {'group_id': int(group_id)}
        )
        server_response = servers.get('response') if isinstance(servers.get('response'), Mapping) else {}
        items = server_response.get('items') if isinstance(server_response.get('items'), list) else []
        existing = next(
            (
                item
                for item in items
                if isinstance(item, Mapping)
                and str(item.get('url') or '').rstrip('/') == callback_url.rstrip('/')
            ),
            None,
        )
        if existing is not None and str(existing.get('id') or '').isdigit():
            server_id = int(existing['id'])
            edited = self._vk_method(
                provider, access_token,
                'groups.editCallbackServer',
                {
                    'group_id': int(group_id),
                    'server_id': server_id,
                    'url': callback_url,
                    'title': 'BusinessAIOS',
                    'secret_key': webhook_secret,
                },
            )
            if edited.get('response') not in {1, '1'}:
                raise RuntimeError('vk_callback_server_edit_rejected')
        else:
            created = self._vk_method(
                provider, access_token,
                'groups.addCallbackServer',
                {
                    'group_id': int(group_id),
                    'url': callback_url,
                    'title': 'BusinessAIOS',
                    'secret_key': webhook_secret,
                },
            )
            created_response = created.get('response')
            raw_server_id = (
                created_response.get('server_id') or created_response.get('id')
                if isinstance(created_response, Mapping)
                else created_response
            )
            if not str(raw_server_id or '').isdigit():
                raise RuntimeError('vk_callback_server_id_missing')
            server_id = int(raw_server_id)
        settings = self._vk_method(
            provider, access_token,
            'groups.setCallbackSettings',
            {
                'group_id': int(group_id),
                'server_id': server_id,
                'api_version': '5.199',
                'message_new': 1,
                'message_event': 1,
            },
        )
        if settings.get('response') not in {1, '1'}:
            raise RuntimeError('vk_callback_settings_rejected')
        verified = self._vk_method(
            provider, access_token, 'groups.getCallbackServers', {'group_id': int(group_id)}
        )
        verified_response = verified.get('response') if isinstance(verified.get('response'), Mapping) else {}
        verified_items = verified_response.get('items') if isinstance(verified_response.get('items'), list) else []
        if not any(
            isinstance(item, Mapping)
            and str(item.get('id') or '') == str(server_id)
            and str(item.get('url') or '').rstrip('/') == callback_url.rstrip('/')
            for item in verified_items
        ):
            raise RuntimeError('vk_callback_server_verification_failed')
        return {
            'provider_state_verified': True,
            'server_id': server_id,
            'event_types': ('message_new', 'message_event'),
            'derived_secret_names': (derived_secret_name,),
        }

    def _reconcile_max(
        self,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
        callback_url: str,
    ) -> dict[str, Any]:
        access_token = self._secret(provider, tenant_id, business_id, 'access_token')
        webhook_secret = self._secret(provider, tenant_id, business_id, 'webhook_secret')
        if not access_token or not webhook_secret:
            raise RuntimeError('max_webhook_credentials_missing')
        url = f"{self._provider_base_url(provider)}/subscriptions"
        headers = {'Authorization': access_token}
        existing = self._json_request(method='GET', url=url, headers=headers)
        if not isinstance(existing, Mapping):
            raise RuntimeError('max_subscription_list_invalid')
        event_types = ('message_created', 'message_callback', 'bot_started')
        configured = self._json_request(
            method='POST',
            url=url,
            headers=headers,
            payload={
                'url': callback_url,
                'update_types': list(event_types),
                'secret': webhook_secret,
            },
        )
        if not isinstance(configured, Mapping) or configured.get('success') is not True:
            raise RuntimeError('max_subscription_rejected')
        verified = self._json_request(method='GET', url=url, headers=headers)
        subscriptions = (
            verified
            if isinstance(verified, list)
            else verified.get('subscriptions') or verified.get('items') or verified.get('data')
            if isinstance(verified, Mapping)
            else None
        )
        if not isinstance(subscriptions, list) or not any(
            isinstance(item, Mapping)
            and str(item.get('url') or '').rstrip('/') == callback_url.rstrip('/')
            for item in subscriptions
        ):
            raise RuntimeError('max_subscription_verification_failed')
        return {
            'provider_state_verified': True,
            'event_types': event_types,
            'subscription_visible': True,
        }


@dataclass(frozen=True)
class ProviderWebhookOperationalResponder:
    secret_vault: SecretVault

    def acknowledge(
        self,
        *,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
        topic: str,
        handoff: Mapping[str, Any],
    ) -> dict[str, Any]:
        if provider.provider_key != 'vk_messaging' or str(topic or '') != 'message_event':
            return {'required': False, 'ok': True}
        inbound = handoff.get('inbound_message') if isinstance(handoff.get('inbound_message'), Mapping) else {}
        event_id = str(inbound.get('transport_message_id') or '').strip()
        user_id = str(inbound.get('user_id') or '').strip()
        peer_id = str(inbound.get('chat_id') or '').strip()
        if not event_id or not user_id or not peer_id:
            return {'required': True, 'ok': False, 'reason': 'vk_message_event_identity_missing'}
        reconciler = ProviderWebhookReconciler(self.secret_vault)
        access_token = reconciler._secret(provider, tenant_id, business_id, 'access_token')
        if not access_token:
            return {'required': True, 'ok': False, 'reason': 'vk_access_token_missing'}
        payload: dict[str, Any] = {
            'event_id': event_id,
            'user_id': user_id,
            'event_data': json.dumps(
                {'type': 'show_snackbar', 'text': 'Готово'},
                ensure_ascii=False,
                separators=(',', ':'),
            ),
        }
        if peer_id:
            payload['peer_id'] = peer_id
        response = reconciler._vk_method(
            provider, access_token, 'messages.sendMessageEventAnswer', payload
        )
        if response.get('response') not in {1, '1'}:
            return {'required': True, 'ok': False, 'reason': 'vk_message_event_ack_rejected'}
        return {
            'required': True,
            'ok': True,
            'kind': 'vk_message_event_answer',
            'event_id': event_id,
        }

__all__ = [
    'CANON_PROVIDER_WEBHOOK_RECONCILIATION',
    'ProviderWebhookOperationalResponder',
    'ProviderWebhookReconciler',
    'ProviderWebhookReconciliationResult',
]
