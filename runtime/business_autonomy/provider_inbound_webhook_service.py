from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_runtime_contract import ProviderWebhookIngressResult
from runtime.business_autonomy.provider_incident_registry import FileProviderIncidentRegistry
from runtime.business_autonomy.provider_runtime_audit import ProviderRuntimeAuditRecorder
from runtime.business_autonomy.provider_runtime_export_bridge import ProviderRuntimeExportBridge
from runtime.business_autonomy.provider_runtime_observability import ProviderRuntimeObservability
from runtime.business_autonomy.provider_webhook_inbound_handoff import build_provider_webhook_inbound_handoff
from runtime.business_autonomy.provider_webhook_inbound_processor import ProviderWebhookInboundProcessor
from runtime.business_autonomy.provider_webhook_inbound_result_summary import summarize_provider_webhook_inbound_result
from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
from runtime.business_autonomy.provider_webhook_route_registry import ProviderWebhookRouteRegistry
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime

CANON_PROVIDER_INBOUND_WEBHOOK_SERVICE = True


@dataclass(frozen=True)
class ProviderInboundWebhookService:
    webhook_runtime: ProviderWebhookRuntime
    replay_guard: ProviderWebhookReplayGuard
    audit_recorder: ProviderRuntimeAuditRecorder = field(default_factory=ProviderRuntimeAuditRecorder.in_memory)
    observability: ProviderRuntimeObservability = field(default_factory=ProviderRuntimeObservability)
    export_bridge: ProviderRuntimeExportBridge = field(default_factory=ProviderRuntimeExportBridge)
    incident_registry: FileProviderIncidentRegistry = field(default_factory=FileProviderIncidentRegistry)
    inbound_processor: ProviderWebhookInboundProcessor | None = None

    def ingest(
        self,
        *,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
        headers: Mapping[str, str],
        body: bytes,
        event_key: str,
        topic: str = '',
        owner_id: str | None = None,
    ) -> ProviderWebhookIngressResult:
        payload_digest = hashlib.sha256(bytes(body)).hexdigest()
        contract = self.webhook_runtime.describe(provider)
        if contract.enabled and not self.webhook_runtime.verify(provider=provider, tenant_id=tenant_id, business_id=business_id, headers=headers, body=body):
            refs = self.audit_recorder.record_webhook_event(
                tenant_id=tenant_id,
                business_id=business_id,
                provider_key=provider.provider_key,
                event_key=event_key,
                status='invalid_signature',
                accepted=False,
                metadata={'topic': topic, 'verification_kind': contract.verification_kind},
            )
            export_refs = self.export_bridge.export_runtime_event(tenant_id=str(tenant_id), business_id=str(business_id), provider_key=provider.provider_key, event_kind='webhook', payload={'status': 'invalid_signature', 'accepted': False, 'topic': str(topic)})
            self.observability.record_webhook(tenant_id=str(tenant_id), provider_key=provider.provider_key, status='invalid_signature', accepted=False, topic=str(topic))
            incident = self.incident_registry.append({'tenant_id': str(tenant_id), 'business_id': str(business_id), 'provider_key': provider.provider_key, 'kind': 'webhook', 'status': 'invalid_signature', 'severity': 'major', 'category': 'webhook_signature', 'message': 'invalid webhook signature', 'metadata': {'topic': topic}})
            route = ProviderWebhookRouteRegistry().extract(provider, headers, body)
            handoff = build_provider_webhook_inbound_handoff(tenant_id=tenant_id, business_id=business_id, provider_key=provider.provider_key, messaging_ingress=route.get('messaging_ingress'), route_metadata=route)
            return ProviderWebhookIngressResult(
                provider_key=provider.provider_key,
                event_key=event_key,
                accepted=False,
                status='invalid_signature',
                metadata={'topic': topic, 'audit_refs': refs, 'export_refs': export_refs, 'route': route, 'messaging_handoff': handoff, 'messaging_inbound_result': {}, 'incident': incident},
            )
        decision = self.replay_guard.reserve_event(
            provider=provider,
            tenant_id=tenant_id,
            business_id=business_id,
            event_key=event_key,
            payload_digest=payload_digest,
            topic=topic,
            owner_id=owner_id,
        )
        status = 'accepted' if decision.accepted else 'replayed'
        refs = self.audit_recorder.record_webhook_event(
            tenant_id=tenant_id,
            business_id=business_id,
            provider_key=provider.provider_key,
            event_key=event_key,
            status=status,
            accepted=decision.accepted,
            metadata={'topic': topic, 'resolution': decision.resolution, 'scope_hash': decision.metadata.get('scope_hash')},
        )
        export_refs = self.export_bridge.export_runtime_event(tenant_id=str(tenant_id), business_id=str(business_id), provider_key=provider.provider_key, event_kind='webhook', payload={'status': status, 'accepted': decision.accepted, 'topic': str(topic)})
        self.observability.record_webhook(tenant_id=str(tenant_id), provider_key=provider.provider_key, status=status, accepted=decision.accepted, topic=str(topic))
        incident = None
        if not decision.accepted:
            incident = self.incident_registry.append({'tenant_id': str(tenant_id), 'business_id': str(business_id), 'provider_key': provider.provider_key, 'kind': 'webhook', 'status': status, 'severity': 'minor', 'category': 'webhook_replay', 'message': 'replayed webhook ignored', 'metadata': {'topic': topic, 'scope_hash': decision.metadata.get('scope_hash')}})
        route = ProviderWebhookRouteRegistry().extract(provider, headers, body)
        handoff = build_provider_webhook_inbound_handoff(tenant_id=tenant_id, business_id=business_id, provider_key=provider.provider_key, messaging_ingress=route.get('messaging_ingress'), route_metadata=route)
        inbound_result = {}
        if decision.accepted and self.inbound_processor is not None and handoff:
            inbound_result = self.inbound_processor.process(handoff=handoff)
        inbound_summary = summarize_provider_webhook_inbound_result(
            handoff=handoff,
            inbound_result=inbound_result,
        )
        self.observability.record_webhook_inbound_handoff(
            tenant_id=str(tenant_id),
            provider_key=provider.provider_key,
            status=status,
            inbound_summary=inbound_summary,
        )
        return ProviderWebhookIngressResult(
            provider_key=provider.provider_key,
            event_key=event_key,
            accepted=decision.accepted,
            status=status,
            metadata={'decision': dict(decision.metadata), 'owner_id': decision.owner_id, 'topic': topic, 'audit_refs': refs, 'export_refs': export_refs, 'route': route, 'messaging_handoff': handoff, 'messaging_inbound_result': inbound_result, 'messaging_inbound_summary': inbound_summary, 'incident': incident},
        )

    def complete(
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
        self.replay_guard.mark_completed(
            provider=provider,
            tenant_id=tenant_id,
            business_id=business_id,
            event_key=event_key,
            payload_digest=payload_digest,
            owner_id=owner_id,
            result_ref=result_ref,
            result_digest=result_digest,
            topic=topic,
        )


__all__ = ['CANON_PROVIDER_INBOUND_WEBHOOK_SERVICE', 'ProviderInboundWebhookService']
