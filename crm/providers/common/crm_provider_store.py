from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_pipeline_contract import CrmPipeline


@dataclass
class ProviderTenantState:
    pipelines: dict[str, CrmPipeline] = field(default_factory=dict)
    contacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    deals: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: dict[str, dict[str, Any]] = field(default_factory=dict)
    idempotency_index: dict[tuple[str, str], str] = field(default_factory=dict)
    audit_log: list[dict[str, Any]] = field(default_factory=list)


class CrmProviderStore:
    """Small in-memory provider store used for hermetic CRM execution.

    This is intentionally deterministic and provider-scoped. It is not a second
    decision layer: it only persists provider-side execution state so that
    write verification, dedup, pipeline provisioning, and state feeds can work
    against real stored records instead of synthetic placeholders.
    """

    def __init__(self, provider_key: str, *, default_pipelines: tuple[CrmPipeline, ...] = ()) -> None:
        self._provider_key = provider_key
        self._default_pipelines = {pipeline.pipeline_key: pipeline for pipeline in default_pipelines}
        self._tenant_state: dict[tuple[str, str], ProviderTenantState] = {}

    def _scope(self, connection: CrmConnectionRef) -> tuple[str, str]:
        return connection.tenant_id, connection.business_id

    def state_for(self, connection: CrmConnectionRef) -> ProviderTenantState:
        key = self._scope(connection)
        state = self._tenant_state.get(key)
        if state is None:
            state = ProviderTenantState(pipelines=dict(self._default_pipelines))
            self._tenant_state[key] = state
        return state

    def verify_connection(self, connection: CrmConnectionRef) -> dict[str, Any]:
        secret_ref = (connection.secret_ref or '').strip()
        provider_matches = connection.provider_key == self._provider_key
        verified = bool(secret_ref) and connection.status in {'authorized', 'active'} and provider_matches
        reason = 'verified' if verified else 'missing_secret_ref' if not secret_ref else 'provider_mismatch' if not provider_matches else 'inactive_connection'
        state = self.state_for(connection) if verified else None
        return {
            'verified': verified,
            'connection_id': connection.connection_id,
            'provider_key': self._provider_key,
            'reason': reason,
            'pipeline_count': len(state.pipelines) if state else 0,
        }

    def list_pipelines(self, connection: CrmConnectionRef) -> tuple[CrmPipeline, ...]:
        state = self.state_for(connection)
        return tuple(sorted(state.pipelines.values(), key=lambda item: item.pipeline_key))

    def upsert_pipeline(self, connection: CrmConnectionRef, pipeline: CrmPipeline, *, idempotency_key: str) -> dict[str, Any]:
        state = self.state_for(connection)
        record_id = pipeline.external_id or f'{self._provider_key}:pipeline:{pipeline.pipeline_key}'
        created = pipeline.pipeline_key not in state.pipelines
        state.pipelines[pipeline.pipeline_key] = pipeline
        state.idempotency_index[('pipeline', idempotency_key)] = record_id
        payload = {
            'operation': 'create' if created else 'update',
            'record_id': record_id,
            'pipeline_key': pipeline.pipeline_key,
            'stage_count': len(pipeline.stages),
            'idempotency_key': idempotency_key,
        }
        state.audit_log.append({'entity_type': 'pipeline', **payload})
        return payload

    def upsert_contact(self, connection: CrmConnectionRef, record: dict[str, Any], *, dedup_key: str, idempotency_key: str) -> dict[str, Any]:
        state = self.state_for(connection)
        existing_id = state.idempotency_index.get(('contact_dedup', dedup_key))
        if existing_id:
            operation = 'update'
            record_id = existing_id
        else:
            operation = 'create'
            record_id = f'{self._provider_key}:contact:{dedup_key}'
        state.contacts[record_id] = dict(record)
        state.idempotency_index[('contact_dedup', dedup_key)] = record_id
        state.idempotency_index[('contact', idempotency_key)] = record_id
        payload = {'operation': operation, 'record_id': record_id, 'dedup_key': dedup_key, 'idempotency_key': idempotency_key}
        state.audit_log.append({'entity_type': 'contact', **payload})
        return payload

    def upsert_deal(self, connection: CrmConnectionRef, record: dict[str, Any], *, dedup_key: str, idempotency_key: str) -> dict[str, Any]:
        state = self.state_for(connection)
        existing_id = state.idempotency_index.get(('deal_dedup', dedup_key))
        if existing_id:
            operation = 'update'
            record_id = existing_id
        else:
            operation = 'create'
            record_id = f'{self._provider_key}:deal:{dedup_key}'
        state.deals[record_id] = dict(record)
        state.idempotency_index[('deal_dedup', dedup_key)] = record_id
        state.idempotency_index[('deal', idempotency_key)] = record_id
        payload = {'operation': operation, 'record_id': record_id, 'dedup_key': dedup_key, 'idempotency_key': idempotency_key}
        state.audit_log.append({'entity_type': 'deal', **payload})
        return payload

    def append_note(self, connection: CrmConnectionRef, record: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        state = self.state_for(connection)
        record_id = state.idempotency_index.get(('note', idempotency_key)) or f'{self._provider_key}:note:{idempotency_key}'
        state.notes[record_id] = dict(record)
        state.idempotency_index[('note', idempotency_key)] = record_id
        payload = {'operation': 'append', 'record_id': record_id, 'idempotency_key': idempotency_key}
        state.audit_log.append({'entity_type': 'note', **payload})
        return payload

    def get_record(self, connection: CrmConnectionRef, *, entity_type: str, record_id: str | None) -> dict[str, Any] | None:
        if not record_id:
            return None
        state = self.state_for(connection)
        bucket_name = {'contact': 'contacts', 'deal': 'deals', 'note': 'notes', 'pipeline': 'pipelines'}.get(entity_type)
        if bucket_name is None:
            return None
        bucket = getattr(state, bucket_name)
        record = bucket.get(record_id)
        if record is None and entity_type == 'pipeline':
            for pipeline in bucket.values():
                if pipeline.external_id == record_id:
                    return {'pipeline_key': pipeline.pipeline_key, 'display_name': pipeline.display_name, 'stage_count': len(pipeline.stages)}
            return None
        if record is None:
            return None
        if isinstance(record, CrmPipeline):
            return {'pipeline_key': record.pipeline_key, 'display_name': record.display_name, 'stage_count': len(record.stages)}
        return dict(record)

    def build_snapshot(self, connection: CrmConnectionRef) -> dict[str, Any]:
        state = self.state_for(connection)
        deals = list(state.deals.values())
        open_deals = sum(1 for deal in deals if not bool(deal.get('is_closed', False)))
        won_deals = sum(1 for deal in deals if bool(deal.get('is_won', False)))
        lost_deals = sum(1 for deal in deals if bool(deal.get('is_closed', False)) and not bool(deal.get('is_won', False)))
        stale_deals = sum(1 for deal in deals if bool(deal.get('is_stale', False)))
        return {
            'pipeline_count': len(state.pipelines),
            'contact_count': len(state.contacts),
            'deal_count': len(state.deals),
            'open_deals': open_deals,
            'won_deals_last_30d': won_deals,
            'lost_deals_last_30d': lost_deals,
            'stalled_deals': stale_deals,
            'recent_activity': tuple(state.audit_log[-10:]),
        }
