from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, UTC
from typing import Any

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import SecretVault

CANON_PROVIDER_SECRET_VERSIONING = True


@dataclass(frozen=True)
class ProviderSecretVersioningService:
    secret_vault: SecretVault

    def archive_current_secret(
        self,
        *,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
        secret_name: str,
        requested_by: str,
        reason: str,
    ) -> str | None:
        current_ref = self._current_ref(tenant_id=tenant_id, provider=provider, business_id=business_id, secret_name=secret_name)
        try:
            plaintext = self.secret_vault.get(current_ref)
        except Exception:
            return None
        version = self._version_label(prefix='v')
        version_ref = SecretRef(
            tenant_id=tenant_id,
            connector_id=provider.connector_id,
            scope=business_id,
            secret_name=f'{provider.connector_id}.{secret_name}',
            version=version,
        )
        record = SecretRecord(
            ref=version_ref,
            ciphertext=b'pending',
            source=SecretSource.CONNECTOR,
            metadata={
                'provider_key': provider.provider_key,
                'business_id': business_id,
                'archived_from': 'current',
                'requested_by': requested_by,
                'reason': reason,
            },
        )
        self.secret_vault.put(record, plaintext=plaintext)
        return version

    def list_versions(
        self,
        *,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
    ) -> tuple[dict[str, Any], ...]:
        rows: list[dict[str, Any]] = []
        for field in provider.secret_fields:
            for record in self._iter_records(tenant_id=tenant_id, provider=provider, business_id=business_id, secret_name=field.secret_name):
                rows.append({
                    'field_key': field.field_key,
                    'secret_name': field.secret_name,
                    'version': record.ref.version,
                    'state': record.state.value,
                    'updated_at': record.updated_at.isoformat(),
                    'rotated_at': None if record.rotated_at is None else record.rotated_at.isoformat(),
                    'metadata': dict(record.metadata or {}),
                })
        rows.sort(key=lambda item: (item['secret_name'], item['updated_at'], item['version']), reverse=True)
        return tuple(rows)

    def rollback_version(
        self,
        *,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
        secret_name: str,
        version: str,
        requested_by: str,
    ) -> dict[str, Any]:
        version_ref = SecretRef(
            tenant_id=tenant_id,
            connector_id=provider.connector_id,
            scope=business_id,
            secret_name=f'{provider.connector_id}.{secret_name}',
            version=str(version).strip(),
        )
        plaintext = self.secret_vault.get(version_ref)
        archived_version = self.archive_current_secret(
            provider=provider,
            tenant_id=tenant_id,
            business_id=business_id,
            secret_name=secret_name,
            requested_by=requested_by,
            reason=f'rollback_to:{version}',
        )
        current_ref = self._current_ref(tenant_id=tenant_id, provider=provider, business_id=business_id, secret_name=secret_name)
        current_record = SecretRecord(
            ref=current_ref,
            ciphertext=b'pending',
            source=SecretSource.CONNECTOR,
            metadata={
                'provider_key': provider.provider_key,
                'business_id': business_id,
                'rollback_from_version': str(version).strip(),
                'requested_by': requested_by,
                'archived_current_version': archived_version or '',
            },
        )
        stored = self.secret_vault.put(current_record, plaintext=plaintext)
        return {
            'provider_key': provider.provider_key,
            'secret_name': secret_name,
            'restored_version': str(version).strip(),
            'archived_current_version': archived_version,
            'updated_at': stored.updated_at.isoformat(),
        }

    def _iter_records(self, *, tenant_id: str, provider: ProviderDefinition, business_id: str, secret_name: str):
        connector_secret_name = f'{provider.connector_id}.{secret_name}'
        backend = getattr(self.secret_vault, '_backend', None)
        if backend is not None and hasattr(backend, 'list_versions'):
            from security.secret_vault_backend import SecretLookup
            lookup = SecretLookup(
                tenant_id=tenant_id,
                connector_id=provider.connector_id,
                scope=business_id,
                secret_name=connector_secret_name,
                version=None,
            )
            try:
                envelopes = backend.list_versions(lookup)
            except Exception:
                envelopes = ()
            for envelope in envelopes:
                yield envelope.record
            return
        if hasattr(self.secret_vault, 'list_records'):
            for record in getattr(self.secret_vault, 'list_records')():
                if record.ref.tenant_id != tenant_id:
                    continue
                if str(record.ref.connector_id or '') != provider.connector_id:
                    continue
                if str(record.ref.scope or '') != business_id:
                    continue
                if record.ref.secret_name != connector_secret_name:
                    continue
                yield record

    @staticmethod
    def _version_label(*, prefix: str) -> str:
        return f"{prefix}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"

    @staticmethod
    def _current_ref(*, tenant_id: str, provider: ProviderDefinition, business_id: str, secret_name: str) -> SecretRef:
        return SecretRef(
            tenant_id=tenant_id,
            connector_id=provider.connector_id,
            scope=business_id,
            secret_name=f'{provider.connector_id}.{secret_name}',
            version='current',
        )


    def mark_compromised(
        self,
        *,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
        secret_name: str,
        requested_by: str,
        reason: str = 'suspected_compromise',
    ) -> dict[str, Any]:
        archived_version = self.archive_current_secret(provider=provider, tenant_id=tenant_id, business_id=business_id, secret_name=secret_name, requested_by=requested_by, reason=reason)
        current_ref = self._current_ref(tenant_id=tenant_id, provider=provider, business_id=business_id, secret_name=secret_name)
        current_record = SecretRecord(
            ref=current_ref,
            ciphertext=b'pending',
            source=SecretSource.CONNECTOR,
            metadata={
                'provider_key': provider.provider_key,
                'business_id': business_id,
                'compromised': True,
                'requested_by': requested_by,
                'reason': reason,
                'archived_current_version': archived_version or '',
            },
        )
        stored = self.secret_vault.put(current_record, plaintext=b'REVOKED_COMPROMISED_SECRET')
        return {
            'provider_key': provider.provider_key,
            'secret_name': secret_name,
            'status': 'marked_compromised',
            'archived_current_version': archived_version,
            'updated_at': stored.updated_at.isoformat(),
        }


__all__ = ['CANON_PROVIDER_SECRET_VERSIONING', 'ProviderSecretVersioningService']
