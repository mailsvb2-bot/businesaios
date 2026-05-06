from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service


CANON_API_PROVIDER_ADMIN_ROUTE_HANDLERS = True


@dataclass(frozen=True)
class ProviderAdminRouteHandlers:
    def _service(self, business_id: str):
        service = build_business_autonomy_guarded_service(business_id=business_id)
        return getattr(service, "_provider_admin_service")

    def list_provider_catalog(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        service = self._service(business_id)
        providers = service.list_provider_definitions()
        statuses = {item.provider_key: item for item in service.list_activation_statuses(tenant_id=tenant_id, business_id=business_id)}
        return {
            "tenant_id": tenant_id,
            "business_id": business_id,
            "providers": [
                {
                    "provider_key": item.provider_key,
                    "title": item.title,
                    "connector_id": item.connector_id,
                    "channel_kind": item.channel_kind.value,
                    "domain": item.domain,
                    "description": item.description,
                    "secret_fields": [
                        {
                            "field_key": field.field_key,
                            "secret_name": field.secret_name,
                            "label": field.label,
                            "placeholder": field.placeholder,
                            "required": field.required,
                            "multiline": field.multiline,
                            "secret_kind": field.secret_kind,
                        }
                        for field in item.secret_fields
                    ],
                    "connected": bool(statuses.get(item.provider_key) and statuses[item.provider_key].connected),
                    "last_updated_utc": None if statuses.get(item.provider_key) is None else statuses[item.provider_key].last_updated_utc,
                }
                for item in providers
            ],
        }

    def list_provider_secret_history(self, *, tenant_id: str, business_id: str, provider_key: str) -> dict[str, Any]:
        rows = self._service(business_id).list_provider_secret_history(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key)
        return {'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'versions': list(rows)}

    def rollback_provider_secret(self, *, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(payload or {})
        result = self._service(str(data.get('business_id') or '').strip()).rollback_provider_secret_version(
            tenant_id=str(data.get('tenant_id') or '').strip(),
            business_id=str(data.get('business_id') or '').strip(),
            provider_key=str(data.get('provider_key') or '').strip(),
            secret_name=str(data.get('secret_name') or '').strip(),
            version=str(data.get('version') or '').strip(),
            requested_by=str(data.get('requested_by') or 'admin_console').strip() or 'admin_console',
        )
        status = result['status']
        return {
            'rollback': dict(result['rollback']),
            'status': {
                'tenant_id': status.tenant_id,
                'business_id': status.business_id,
                'provider_key': status.provider_key,
                'connected': status.connected,
                'last_updated_utc': status.last_updated_utc,
                'metadata': dict(status.metadata),
            },
        }

    def get_provider_runtime_routes(self, *, provider_key: str) -> dict[str, Any]:
        return self._service('default-business').describe_provider_runtime_routes(provider_key=provider_key)


    def probe_provider_live(self, *, tenant_id: str, business_id: str, provider_key: str, mode: str = 'dry_run') -> dict[str, Any]:
        return self._service(business_id).probe_provider_live(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, mode=mode)

    def paginate_provider_sync(self, *, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(payload or {})
        return self._service(str(data.get('business_id') or '').strip()).paginate_provider_sync(
            tenant_id=str(data.get('tenant_id') or '').strip(),
            business_id=str(data.get('business_id') or '').strip(),
            provider_key=str(data.get('provider_key') or '').strip(),
            operation=str(data.get('operation') or '').strip(),
            mode=str(data.get('mode') or 'dry_run').strip() or 'dry_run',
            payload=dict(data.get('payload') or {}),
            max_pages=int(data.get('max_pages', 3) or 3),
        )

    def mark_provider_secret_compromised(self, *, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(payload or {})
        result = self._service(str(data.get('business_id') or '').strip()).mark_provider_secret_compromised(tenant_id=str(data.get('tenant_id') or '').strip(), business_id=str(data.get('business_id') or '').strip(), provider_key=str(data.get('provider_key') or '').strip(), secret_name=str(data.get('secret_name') or '').strip(), requested_by=str(data.get('requested_by') or 'admin_console').strip() or 'admin_console', reason=str(data.get('reason') or 'suspected_compromise').strip() or 'suspected_compromise')
        status = result['status']
        return {'compromise': dict(result['compromise']), 'status': {'tenant_id': status.tenant_id, 'business_id': status.business_id, 'provider_key': status.provider_key, 'connected': status.connected, 'last_updated_utc': status.last_updated_utc, 'metadata': dict(status.metadata)}}

    def schedule_provider_retry(self, *, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(payload or {})
        return self._service(str(data.get('business_id') or '').strip()).schedule_provider_retry(tenant_id=str(data.get('tenant_id') or '').strip(), business_id=str(data.get('business_id') or '').strip(), provider_key=str(data.get('provider_key') or '').strip(), operation=str(data.get('operation') or '').strip(), category=str(data.get('category') or '').strip(), retryable=bool(data.get('retryable', True)))

    def list_provider_retry_jobs(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 20) -> dict[str, Any]:
        rows = self._service(business_id).list_provider_retry_jobs(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=limit)
        return {'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'jobs': list(rows)}

    def list_provider_export_history(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 20) -> dict[str, Any]:
        rows = self._service(business_id).list_provider_export_history(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=limit)
        return {'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'exports': list(rows)}

    def activate_provider(self, *, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(payload or {})
        submission = ProviderCredentialSubmission(
            tenant_id=str(data.get("tenant_id") or "").strip(),
            business_id=str(data.get("business_id") or "").strip(),
            provider_key=str(data.get("provider_key") or "").strip(),
            ownership_key=str(data.get("ownership_key") or "").strip(),
            requested_by=str(data.get("requested_by") or "admin_console").strip() or "admin_console",
            external_ref=str(data.get("external_ref") or "").strip(),
            region=None if data.get("region") in {None, ""} else str(data.get("region")),
            metadata=dict(data.get("metadata") or {}),
            secrets={str(k): str(v) for k, v in dict(data.get("secrets") or {}).items()},
        )
        status = self._service(submission.business_id).activate_provider(submission)
        return {
            "tenant_id": status.tenant_id,
            "business_id": status.business_id,
            "provider_key": status.provider_key,
            "connected": status.connected,
            "connector_id": status.connector_id,
            "channel_kind": status.channel_kind,
            "secret_fields_bound": list(status.secret_fields_bound),
            "persistent_surfaces": list(status.persistent_surfaces),
            "governance_enabled": status.governance_enabled,
            "onboarding_ready": status.onboarding_ready,
            "last_updated_utc": status.last_updated_utc,
            "metadata": dict(status.metadata),
        }

    def revoke_provider(self, *, tenant_id: str, business_id: str, provider_key: str, requested_by: str = 'admin_console') -> dict[str, Any]:
        status = self._service(business_id).revoke_provider(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, requested_by=requested_by)
        return {'tenant_id': status.tenant_id, 'business_id': status.business_id, 'provider_key': status.provider_key, 'connected': status.connected, 'onboarding_ready': status.onboarding_ready, 'last_updated_utc': status.last_updated_utc, 'metadata': dict(status.metadata)}

    def reconnect_provider(self, *, tenant_id: str, business_id: str, provider_key: str, requested_by: str = 'admin_console', probe_mode: str = 'dry_run', activate_runtime: bool = False) -> dict[str, Any]:
        status = self._service(business_id).reconnect_provider(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, requested_by=requested_by, probe_mode=probe_mode, activate_runtime=activate_runtime)
        return {'tenant_id': status.tenant_id, 'business_id': status.business_id, 'provider_key': status.provider_key, 'connected': status.connected, 'onboarding_ready': status.onboarding_ready, 'last_updated_utc': status.last_updated_utc, 'metadata': dict(status.metadata)}

    def rotate_provider(self, *, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(payload or {})
        tenant_id = str(data.get('tenant_id') or '').strip()
        business_id = str(data.get('business_id') or '').strip()
        provider_key = str(data.get('provider_key') or '').strip()
        requested_by = str(data.get('requested_by') or 'admin_console').strip() or 'admin_console'
        secrets = {str(k): str(v) for k, v in dict(data.get('secrets') or {}).items()}
        status = self._service(business_id).rotate_provider_secrets(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, secrets=secrets, requested_by=requested_by)
        return {'tenant_id': status.tenant_id, 'business_id': status.business_id, 'provider_key': status.provider_key, 'connected': status.connected, 'onboarding_ready': status.onboarding_ready, 'last_updated_utc': status.last_updated_utc, 'metadata': dict(status.metadata)}

    def trigger_provider_sync(self, *, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(payload or {})
        return self._service(str(data.get('business_id') or '').strip()).trigger_provider_sync(tenant_id=str(data.get('tenant_id') or '').strip(), business_id=str(data.get('business_id') or '').strip(), provider_key=str(data.get('provider_key') or '').strip(), operation=str(data.get('operation') or '').strip(), mode=str(data.get('mode') or 'dry_run').strip() or 'dry_run', payload=dict(data.get('payload') or {}))

    def ingest_provider_webhook(self, *, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(payload or {})
        headers = {str(k): str(v) for k, v in dict(data.get('headers') or {}).items()}
        body = str(data.get('body') or '').encode('utf-8')
        return self._service(str(data.get('business_id') or '').strip()).ingest_provider_webhook(tenant_id=str(data.get('tenant_id') or '').strip(), business_id=str(data.get('business_id') or '').strip(), provider_key=str(data.get('provider_key') or '').strip(), headers=headers, body=body, event_key=str(data.get('event_key') or '').strip(), topic=str(data.get('topic') or '').strip(), owner_id=str(data.get('owner_id') or 'provider_admin').strip() or 'provider_admin')

    def enqueue_provider_sync(self, *, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(payload or {})
        return self._service(str(data.get('business_id') or '').strip()).enqueue_provider_sync(tenant_id=str(data.get('tenant_id') or '').strip(), business_id=str(data.get('business_id') or '').strip(), provider_key=str(data.get('provider_key') or '').strip(), operation=str(data.get('operation') or '').strip(), mode=str(data.get('mode') or 'live').strip() or 'live', payload=dict(data.get('payload') or {}))

    def tick_provider_sync_queue(self, *, tenant_id: str, worker_id: str = 'provider-runtime-worker') -> dict[str, Any]:
        return self._service('default-business').tick_provider_sync_queue(tenant_id=tenant_id, worker_id=worker_id)

    def list_provider_queue_jobs(self, *, tenant_id: str, business_id: str | None = None, provider_key: str, limit: int = 50) -> dict[str, Any]:
        service_business_id = str(business_id or 'default-business').strip()
        rows = self._service(service_business_id).list_provider_queue_jobs(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=limit)
        return {'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'jobs': list(rows)}

    def list_provider_sync_history(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> dict[str, Any]:
        rows = self._service(business_id).list_provider_sync_history(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=limit)
        return {'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'history': list(rows)}

    def list_provider_runtime_incidents(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> dict[str, Any]:
        rows = self._service(business_id).list_provider_runtime_incidents(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=limit)
        return {'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'incidents': list(rows)}

    def describe_provider_response_parser(self, *, provider_key: str) -> dict[str, Any]:
        return self._service('default-business').describe_provider_response_parser(provider_key=provider_key)

    def describe_provider_live_client(self, *, provider_key: str) -> dict[str, Any]:
        return self._service('default-business').describe_provider_live_client(provider_key=provider_key)


    def dispatch_provider_queue(self, *, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.enqueue_provider_sync(payload=payload)

    def tick_provider_queue(self, *, tenant_id: str) -> dict[str, Any]:
        return self.tick_provider_sync_queue(tenant_id=tenant_id)

    def get_provider_live_client(self, *, provider_key: str) -> dict[str, Any]:
        return self.describe_provider_live_client(provider_key=provider_key)

    def get_provider_queue_metrics(self, *, tenant_id: str) -> dict[str, Any]:
        return self._service('default-business').get_provider_queue_metrics(tenant_id=tenant_id)


__all__ = ["CANON_API_PROVIDER_ADMIN_ROUTE_HANDLERS", "ProviderAdminRouteHandlers"]
