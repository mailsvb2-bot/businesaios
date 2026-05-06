from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from security.governance_journal import SQLiteGovernanceJournal
from security.kms_provider_backend import KMSProviderSelectionRequest
from security.kms_provider_contract import KMSKeyHandle
from security.kms_provider_registry import KMSProviderRegistry
from security.security_audit_export_service import SecurityAuditExportService
from security.external_adapter_credentials import ExternalAdapterCredential, assert_external_adapter_credential
from security.reencryption_job_store import ReencryptionJob, SQLiteReencryptionJobStore
from security.security_drill_schedule_store import SQLiteSecurityDrillScheduleStore, SecurityDrillSchedule

CANON_TENANT_SECURITY_ISOLATION = True

@dataclass(frozen=True)
class TenantScopedSecurityView:
    tenant_id: str
    governance_events: tuple[dict[str, object], ...]
    reencryption_jobs: tuple[ReencryptionJob, ...]
    drill_schedules: tuple[SecurityDrillSchedule, ...]


class TenantSecurityIsolationError(PermissionError):
    """Raised when a tenant attempts to access another tenant's security surface."""


class TenantScopedSecurityIsolation:
    def __init__(self, *, governance_journal: SQLiteGovernanceJournal, reencryption_jobs: SQLiteReencryptionJobStore, drill_schedule_store: SQLiteSecurityDrillScheduleStore, kms_registry: KMSProviderRegistry | None = None, audit_export_service: SecurityAuditExportService | None = None) -> None:
        self._journal = governance_journal
        self._jobs = reencryption_jobs
        self._drills = drill_schedule_store
        self._kms_registry = kms_registry
        self._audit_export_service = audit_export_service

    @staticmethod
    def _tenant_norm(tenant_id: str) -> str:
        tenant_norm = str(tenant_id or '').strip()
        if not tenant_norm:
            raise ValueError('tenant_id is required')
        return tenant_norm

    def assert_tenant_match(self, *, requester_tenant_id: str, target_tenant_id: str | None, surface: str) -> None:
        requester = self._tenant_norm(requester_tenant_id)
        target = self._tenant_norm(target_tenant_id or '')
        if requester != target:
            raise TenantSecurityIsolationError(f'cross-tenant {surface} access denied')

    def build_view(self, *, tenant_id: str) -> TenantScopedSecurityView:
        tenant_norm = self._tenant_norm(tenant_id)
        events = tuple(self._journal.latest_for_tenant(tenant_id=tenant_norm, limit=500))
        jobs = self._jobs.list_active_for_tenant(tenant_id=tenant_norm)
        drills = tuple(self._drills.list_enabled_for_tenant(tenant_id=tenant_norm))
        return TenantScopedSecurityView(tenant_id=tenant_norm, governance_events=events, reencryption_jobs=jobs, drill_schedules=drills)

    def latest_governance_events(self, *, tenant_id: str, limit: int = 100) -> tuple[dict[str, Any], ...]:
        tenant_norm = self._tenant_norm(tenant_id)
        return tuple(self._journal.latest_for_tenant(tenant_id=tenant_norm, limit=limit))

    def latest_entity_timeline(self, *, tenant_id: str, entity_kind: str, entity_id: str, limit: int = 100) -> tuple[dict[str, Any], ...]:
        tenant_norm = self._tenant_norm(tenant_id)
        return tuple(self._journal.latest_entity_timeline_for_tenant(tenant_id=tenant_norm, entity_kind=entity_kind, entity_id=entity_id, limit=limit))

    @staticmethod
    def _tenant_key_prefix(tenant_id: str) -> str:
        tenant_norm = str(tenant_id or '').strip()
        if not tenant_norm:
            raise ValueError('tenant_id is required')
        return f'tenant:{tenant_norm}:'

    def _assert_tenant_key_id(self, *, tenant_id: str, key_id: str) -> None:
        key_norm = str(key_id or '').strip()
        if not key_norm.startswith(self._tenant_key_prefix(tenant_id)):
            raise TenantSecurityIsolationError('cross-tenant kms key access denied')

    def _assert_tenant_payload(self, *, tenant_id: str, payload: dict[str, Any], surface: str) -> None:
        payload_tenant = str(dict(payload or {}).get('tenant_id', '')).strip()
        if payload_tenant and payload_tenant != self._tenant_norm(tenant_id):
            raise TenantSecurityIsolationError(f'cross-tenant {surface} payload denied')

    def get_reencryption_job(self, *, tenant_id: str, job_id: str) -> ReencryptionJob:
        tenant_norm = self._tenant_norm(tenant_id)
        try:
            return self._jobs.get_for_tenant(tenant_id=tenant_norm, job_id=job_id)
        except PermissionError as exc:
            raise TenantSecurityIsolationError(str(exc)) from exc

    def get_drill_schedule(self, *, tenant_id: str, drill_id: str) -> SecurityDrillSchedule:
        tenant_norm = self._tenant_norm(tenant_id)
        try:
            return self._drills.get_for_tenant(tenant_id=tenant_norm, drill_id=drill_id)
        except PermissionError as exc:
            raise TenantSecurityIsolationError(str(exc)) from exc


    def _provider_name_for_selection(self, *, preferred_provider_name: str | None, require_hsm_backed_keys: bool, operation_kind: str) -> str:
        if self._kms_registry is None:
            raise RuntimeError('kms_registry is not configured')
        _provider, selection = self._kms_registry.select(
            KMSProviderSelectionRequest(
                operation_kind=operation_kind,
                require_hsm_backed_keys=bool(require_hsm_backed_keys),
                preferred_provider_name=preferred_provider_name,
            )
        )
        return selection.provider_name

    def get_tenant_active_kms_key(self, *, tenant_id: str, key_id: str, preferred_provider_name: str | None = None, require_hsm_backed_keys: bool = True, credential: ExternalAdapterCredential | None = None) -> KMSKeyHandle:
        tenant_norm = self._tenant_norm(tenant_id)
        self._assert_tenant_key_id(tenant_id=tenant_norm, key_id=key_id)
        if self._kms_registry is None:
            raise RuntimeError('kms_registry is not configured')
        provider_name = self._provider_name_for_selection(preferred_provider_name=preferred_provider_name, require_hsm_backed_keys=require_hsm_backed_keys, operation_kind='get_active_key')
        resolved_credential = assert_external_adapter_credential(tenant_id=tenant_norm, credential=credential, provider_name=provider_name)
        provider = self._kms_registry.get(provider_name)
        handle = provider.get_active_key(key_id=str(key_id), credential_ref=resolved_credential.credential_ref)
        self._assert_tenant_key_id(tenant_id=tenant_norm, key_id=handle.key_id)
        return handle


    def create_tenant_kms_key(self, *, tenant_id: str, key_id: str, algorithm: str, preferred_provider_name: str | None = None, require_hsm_backed_keys: bool = True, exportable: bool = False, credential: ExternalAdapterCredential | None = None) -> KMSKeyHandle:
        tenant_norm = self._tenant_norm(tenant_id)
        self._assert_tenant_key_id(tenant_id=tenant_norm, key_id=key_id)
        if self._kms_registry is None:
            raise RuntimeError('kms_registry is not configured')
        provider_name = self._provider_name_for_selection(preferred_provider_name=preferred_provider_name, require_hsm_backed_keys=require_hsm_backed_keys, operation_kind='create_key')
        resolved_credential = assert_external_adapter_credential(tenant_id=tenant_norm, credential=credential, provider_name=provider_name)
        provider = self._kms_registry.get(provider_name)
        handle = provider.create_key(key_id=str(key_id), algorithm=str(algorithm), exportable=bool(exportable), credential_ref=resolved_credential.credential_ref)
        self._assert_tenant_key_id(tenant_id=tenant_norm, key_id=handle.key_id)
        return handle

    def rotate_tenant_kms_key(self, *, tenant_id: str, key_id: str, algorithm: str, preferred_provider_name: str | None = None, require_hsm_backed_keys: bool = True, credential: ExternalAdapterCredential | None = None) -> KMSKeyHandle:
        return self.create_tenant_kms_key(tenant_id=tenant_id, key_id=key_id, algorithm=algorithm, preferred_provider_name=preferred_provider_name, require_hsm_backed_keys=require_hsm_backed_keys, exportable=False, credential=credential)

    def export_tenant_notarized_bundle(self, *, tenant_id: str, payload: dict[str, Any], certification: dict[str, Any] | None = None, credential: ExternalAdapterCredential | None = None) -> dict[str, object]:
        tenant_norm = self._tenant_norm(tenant_id)
        if self._audit_export_service is None:
            raise RuntimeError('audit_export_service is not configured')
        resolved_credential = assert_external_adapter_credential(tenant_id=tenant_norm, credential=credential, provider_name='local-notary')
        payload_dict = dict(payload)
        payload_dict.setdefault('tenant_id', tenant_norm)
        self._assert_tenant_payload(tenant_id=tenant_norm, payload=payload_dict, surface='audit-export')
        cert = dict(certification or {})
        cert.setdefault('tenant_id', tenant_norm)
        return self._audit_export_service.export_bundle(payload=payload_dict, certification=cert, credential_ref=resolved_credential.credential_ref)

    def verify_tenant_notarized_bundle(self, *, tenant_id: str, exported_bundle: dict[str, Any], credential: ExternalAdapterCredential | None = None) -> bool:
        tenant_norm = self._tenant_norm(tenant_id)
        bundle = dict(exported_bundle.get('bundle') or {})
        signed_payload = dict(bundle.get('signed_payload') or {})
        payload = dict(signed_payload.get('payload') or {})
        certification = dict(bundle.get('certification') or {})
        self._assert_tenant_payload(tenant_id=tenant_norm, payload=payload, surface='audit-export')
        self._assert_tenant_payload(tenant_id=tenant_norm, payload=certification, surface='audit-certification')
        if self._audit_export_service is None:
            raise RuntimeError('audit_export_service is not configured')
        resolved_credential = assert_external_adapter_credential(tenant_id=tenant_norm, credential=credential, provider_name='local-notary')
        return bool(self._audit_export_service.verify_bundle(exported_bundle=exported_bundle))

__all__ = ['CANON_TENANT_SECURITY_ISOLATION', 'TenantSecurityIsolationError', 'TenantScopedSecurityIsolation', 'TenantScopedSecurityView']
