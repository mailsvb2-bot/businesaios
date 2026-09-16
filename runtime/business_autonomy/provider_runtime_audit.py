from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from contracts.owner_decision_provenance import normalize_owner_decision_provenance
from storage.audit_store import AuditRecord, InMemoryAuditStore
from storage.evidence_store import EvidenceRecord, InMemoryEvidenceStore

CANON_PROVIDER_RUNTIME_AUDIT = True


@dataclass(frozen=True)
class ProviderRuntimeAuditRecorder:
    audit_store: Any
    evidence_store: Any

    @classmethod
    def in_memory(cls) -> ProviderRuntimeAuditRecorder:
        return cls(audit_store=InMemoryAuditStore(), evidence_store=InMemoryEvidenceStore())

    def record_sync_run(
        self,
        *,
        tenant_id: str,
        business_id: str,
        provider_key: str,
        operation: str,
        mode: str,
        status: str,
        accepted: bool,
        payload: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> dict[str, str]:
        provenance = normalize_owner_decision_provenance(
            dict(metadata or {}).get('decision_provenance')
        )
        if provenance and (
            str(provenance['tenant_id']) != str(tenant_id)
            or str(provenance['business_id']) != str(business_id)
        ):
            raise ValueError('provider evidence decision provenance scope mismatch')
        audit = self.audit_store.append(
            AuditRecord(
                tenant_id=str(tenant_id),
                scope='provider_runtime',
                actor='provider_live_sync_runtime',
                action=f'sync_{status}',
                entity_type='provider_connector',
                entity_id=f'{business_id}:{provider_key}',
                payload={
                    'provider_key': provider_key,
                    'operation': operation,
                    'mode': mode,
                    'accepted': bool(accepted),
                    'payload': dict(payload or {}),
                    'metadata': dict(metadata or {}),
                },
                labels={'provider_key': provider_key, 'business_id': str(business_id), 'mode': mode},
            )
        )
        provider_action_ref = f'{business_id}:{provider_key}:{operation}'
        lineage = {
            'source': f'provider:{provider_key}',
            'normalization': audit.event_id,
            'action': str(provenance.get('action_id') or provider_action_ref),
            'outcome': f'{business_id}:{provider_key}:{operation}:{status}',
        }
        if provenance:
            lineage['decision'] = str(provenance['decision_id'])
        evidence = self.evidence_store.append(
            EvidenceRecord(
                tenant_id=str(tenant_id),
                scope='provider_runtime',
                run_id=str(provenance.get('run_id') or f'{provider_key}:{operation}:{mode}'),
                action_type='provider_sync',
                verification_status='accepted' if accepted else 'rejected',
                action_id=str(provenance.get('action_id') or provider_action_ref),
                source=str(provider_key),
                source_type='provider_sync',
                business_id=str(business_id),
                observed_at=audit.created_at,
                privacy_class='internal',
                retention_policy='provider_runtime_evidence',
                lineage=lineage,
                payload={'status': status, 'metadata': dict(metadata or {})},
                refs=tuple(
                    dict.fromkeys(
                        value
                        for value in (
                            audit.event_id,
                            str(provenance.get('run_id') or ''),
                            str(provenance.get('decision_id') or ''),
                            str(provenance.get('action_id') or ''),
                        )
                        if value
                    )
                ),
                labels={
                    'provider_key': provider_key,
                    'business_id': str(business_id),
                    **({'decision_id': str(provenance['decision_id'])} if provenance else {}),
                },
            )
        )
        return {'audit_event_id': audit.event_id, 'evidence_id': evidence.evidence_id}

    def record_webhook_event(
        self,
        *,
        tenant_id: str,
        business_id: str,
        provider_key: str,
        event_key: str,
        status: str,
        accepted: bool,
        metadata: Mapping[str, Any],
    ) -> dict[str, str]:
        audit = self.audit_store.append(
            AuditRecord(
                tenant_id=str(tenant_id),
                scope='provider_webhook',
                actor='provider_webhook_runtime',
                action=f'webhook_{status}',
                entity_type='provider_connector',
                entity_id=f'{business_id}:{provider_key}',
                payload={'provider_key': provider_key, 'event_key': event_key, 'accepted': bool(accepted), 'metadata': dict(metadata or {})},
                labels={'provider_key': provider_key, 'business_id': str(business_id)},
            )
        )
        evidence = self.evidence_store.append(
            EvidenceRecord(
                tenant_id=str(tenant_id),
                scope='provider_webhook',
                run_id=f'{provider_key}:{event_key}',
                action_type='provider_webhook',
                verification_status='accepted' if accepted else 'rejected',
                action_id=f'{business_id}:{provider_key}:{event_key}',
                source=str(provider_key),
                source_type='provider_webhook',
                business_id=str(business_id),
                observed_at=audit.created_at,
                privacy_class='internal',
                retention_policy='provider_runtime_evidence',
                lineage={
                    'source': f'provider:{provider_key}',
                    'normalization': audit.event_id,
                    'action': f'{business_id}:{provider_key}:{event_key}',
                    'outcome': f'{business_id}:{provider_key}:{event_key}:{status}',
                },
                payload={'status': status, 'metadata': dict(metadata or {})},
                refs=(audit.event_id,),
                labels={'provider_key': provider_key, 'business_id': str(business_id)},
            )
        )
        return {'audit_event_id': audit.event_id, 'evidence_id': evidence.evidence_id}


__all__ = ['CANON_PROVIDER_RUNTIME_AUDIT', 'ProviderRuntimeAuditRecorder']
