from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_runtime_contract import ProviderWebhookReplayDecision
from reliability.idempotency_contract import IdempotencyResolution, IdempotencyStore
from reliability.idempotency_scope import build_idempotency_key

CANON_PROVIDER_WEBHOOK_REPLAY_GUARD = True


@dataclass(frozen=True)
class ProviderWebhookReplayGuard:
    idempotency_store: IdempotencyStore
    owner_prefix: str = 'provider-webhook'

    def reserve_event(
        self,
        *,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
        event_key: str,
        payload_digest: str,
        topic: str = '',
        owner_id: str | None = None,
        lease_ttl_seconds: int = 300,
    ) -> ProviderWebhookReplayDecision:
        normalized_event = str(event_key or '').strip()
        if not normalized_event:
            raise ValueError('event_key is required')
        normalized_owner = str(owner_id or f"{self.owner_prefix}:{provider.provider_key}:{business_id}").strip()
        key = build_idempotency_key(
            tenant_id=tenant_id,
            namespace='provider_webhook',
            operation=provider.provider_key,
            key=normalized_event,
            semantic_scope={
                'tenant_id': str(tenant_id),
                'business_id': str(business_id),
                'provider_key': provider.provider_key,
                'event_key': normalized_event,
                'payload_digest': str(payload_digest or '').strip(),
                'topic': str(topic or '').strip(),
            },
        )
        decision = self.idempotency_store.reserve(
            key=key,
            owner_id=normalized_owner,
            lease_ttl_seconds=lease_ttl_seconds,
            metadata_patch={'business_id': str(business_id), 'provider_key': provider.provider_key, 'topic': str(topic or '').strip(), 'payload_digest': str(payload_digest or '').strip()},
        )
        accepted = decision.resolution is IdempotencyResolution.ACCEPTED
        return ProviderWebhookReplayDecision(
            provider_key=provider.provider_key,
            event_key=normalized_event,
            resolution=decision.resolution.value,
            accepted=accepted,
            owner_id=normalized_owner,
            metadata={
                'scope_hash': key.scope_hash,
                'namespace': key.namespace,
                'operation': key.operation,
                'record_state': decision.record.state.value,
                'replay_result_ref': decision.replay_result_ref,
                'replay_result_digest': decision.replay_result_digest,
            },
        )

    def mark_completed(
        self,
        *,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
        event_key: str,
        payload_digest: str,
        owner_id: str,
        result_ref: str = '',
        result_digest: str = '',
        topic: str = '',
    ) -> None:
        key = build_idempotency_key(
            tenant_id=tenant_id,
            namespace='provider_webhook',
            operation=provider.provider_key,
            key=str(event_key).strip(),
            semantic_scope={
                'tenant_id': str(tenant_id),
                'business_id': str(business_id),
                'provider_key': provider.provider_key,
                'event_key': str(event_key).strip(),
                'payload_digest': str(payload_digest or '').strip(),
                'topic': str(topic or '').strip(),
            },
        )
        self.idempotency_store.mark_completed(
            key=key,
            owner_id=str(owner_id).strip(),
            result_ref=str(result_ref or '').strip() or None,
            result_digest=str(result_digest or '').strip() or None,
            metadata_patch={'provider_key': provider.provider_key, 'business_id': str(business_id)},
        )


__all__ = ['CANON_PROVIDER_WEBHOOK_REPLAY_GUARD', 'ProviderWebhookReplayGuard']
