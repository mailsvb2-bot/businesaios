from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field

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
        raw_digest = hashlib.sha256(bytes(body)).hexdigest()
        requested_event_key = str(event_key or '').strip()
        routes = ProviderWebhookRouteRegistry().extract_many(provider, headers, body)
        first_route = routes[0]
        route_event_key = str(first_route.get('event_key') or f'{provider.provider_key}:{raw_digest[:24]}')
        effective_event_key = route_event_key if provider.provider_key in {'line_messaging', 'viber_messaging'} else (requested_event_key if requested_event_key and requested_event_key != 'payload-digest-fallback' else route_event_key)
        effective_topic = str(topic or '').strip() or str(first_route.get('topic') or '')
        contract = self.webhook_runtime.describe(provider)
        if contract.enabled and not self.webhook_runtime.verify(provider=provider, tenant_id=tenant_id, business_id=business_id, headers=headers, body=body):
            refs = self.audit_recorder.record_webhook_event(tenant_id=tenant_id, business_id=business_id, provider_key=provider.provider_key, event_key=effective_event_key, status='invalid_signature', accepted=False, metadata={'topic': effective_topic, 'verification_kind': contract.verification_kind})
            export_refs = self.export_bridge.export_runtime_event(tenant_id=str(tenant_id), business_id=str(business_id), provider_key=provider.provider_key, event_kind='webhook', payload={'status': 'invalid_signature', 'accepted': False, 'topic': effective_topic})
            self.observability.record_webhook(tenant_id=str(tenant_id), provider_key=provider.provider_key, status='invalid_signature', accepted=False, topic=effective_topic)
            incident = self.incident_registry.append({'tenant_id': str(tenant_id), 'business_id': str(business_id), 'provider_key': provider.provider_key, 'kind': 'webhook', 'status': 'invalid_signature', 'severity': 'major', 'category': 'webhook_signature', 'message': 'invalid webhook signature', 'metadata': {'topic': effective_topic}})
            handoff = build_provider_webhook_inbound_handoff(tenant_id=tenant_id, business_id=business_id, provider_key=provider.provider_key, messaging_ingress=first_route.get('messaging_ingress'), route_metadata=first_route)
            return ProviderWebhookIngressResult(provider_key=provider.provider_key, event_key=effective_event_key, accepted=False, status='invalid_signature', metadata={'topic': effective_topic, 'audit_refs': refs, 'export_refs': export_refs, 'route': first_route, 'messaging_handoff': handoff, 'messaging_inbound_result': {}, 'incident': incident})
        if len(routes) == 1:
            return self._ingest_verified_route(provider=provider, tenant_id=tenant_id, business_id=business_id, route=first_route, event_key=effective_event_key, topic=effective_topic, owner_id=owner_id)
        results = tuple(self._ingest_verified_route(provider=provider, tenant_id=tenant_id, business_id=business_id, route=route, event_key=str(route.get('event_key') or ''), topic=str(route.get('topic') or ''), owner_id=owner_id) for route in routes)
        batch_results = tuple({'event_key': result.event_key, 'accepted': result.accepted, 'status': result.status, 'metadata': dict(result.metadata or {})} for result in results)
        return ProviderWebhookIngressResult(provider_key=provider.provider_key, event_key=f'{provider.provider_key}:batch:{raw_digest[:24]}', accepted=any(result.accepted for result in results), status='accepted' if any(result.accepted for result in results) else 'replayed', metadata={'batch_event_count': len(results), 'batch_results': batch_results, 'batch_transport_ack_safe': all(self.transport_ack_safe(result) for result in results)})

    def _ingest_verified_route(
        self,
        *,
        provider: ProviderDefinition,
        tenant_id: str,
        business_id: str,
        route: Mapping[str, object],
        event_key: str,
        topic: str,
        owner_id: str | None,
    ) -> ProviderWebhookIngressResult:
        payload_digest = str(route.get('payload_digest') or '').strip()
        event_key = str(event_key or '').strip() or f'{provider.provider_key}:{payload_digest[:24]}'
        decision = self.replay_guard.reserve_event(provider=provider, tenant_id=tenant_id, business_id=business_id, event_key=event_key, payload_digest=payload_digest, topic=topic, owner_id=owner_id)
        status = 'accepted' if decision.accepted else 'replayed'
        refs = self.audit_recorder.record_webhook_event(tenant_id=tenant_id, business_id=business_id, provider_key=provider.provider_key, event_key=event_key, status=status, accepted=decision.accepted, metadata={'topic': topic, 'resolution': decision.resolution, 'scope_hash': decision.metadata.get('scope_hash')})
        export_refs = self.export_bridge.export_runtime_event(tenant_id=str(tenant_id), business_id=str(business_id), provider_key=provider.provider_key, event_kind='webhook', payload={'status': status, 'accepted': decision.accepted, 'topic': topic})
        self.observability.record_webhook(tenant_id=str(tenant_id), provider_key=provider.provider_key, status=status, accepted=decision.accepted, topic=topic)
        incident = None if decision.accepted else self.incident_registry.append({'tenant_id': str(tenant_id), 'business_id': str(business_id), 'provider_key': provider.provider_key, 'kind': 'webhook', 'status': status, 'severity': 'minor', 'category': 'webhook_replay', 'message': 'replayed webhook ignored', 'metadata': {'topic': topic, 'scope_hash': decision.metadata.get('scope_hash')}})
        handoff = build_provider_webhook_inbound_handoff(tenant_id=tenant_id, business_id=business_id, provider_key=provider.provider_key, messaging_ingress=route.get('messaging_ingress'), route_metadata=route)
        inbound_result = self.inbound_processor.process(handoff=handoff) if decision.accepted and self.inbound_processor is not None and handoff else {}
        if decision.accepted and (not handoff or inbound_result):
            self.complete(provider=provider, tenant_id=tenant_id, business_id=business_id, event_key=event_key, payload_digest=payload_digest, owner_id=decision.owner_id, topic=topic)
        inbound_summary = summarize_provider_webhook_inbound_result(handoff=handoff, inbound_result=inbound_result)
        self.observability.record_webhook_inbound_handoff(tenant_id=str(tenant_id), provider_key=provider.provider_key, status=status, inbound_summary=inbound_summary)
        return ProviderWebhookIngressResult(provider_key=provider.provider_key, event_key=event_key, accepted=decision.accepted, status=status, metadata={'decision': {'resolution': decision.resolution, **dict(decision.metadata)}, 'owner_id': decision.owner_id, 'topic': topic, 'audit_refs': refs, 'export_refs': export_refs, 'route': dict(route), 'messaging_handoff': handoff, 'messaging_inbound_result': inbound_result, 'messaging_inbound_summary': inbound_summary, 'incident': incident})

    @staticmethod
    def transport_ack_safe(result: ProviderWebhookIngressResult) -> bool:
        metadata = dict(result.metadata or {})
        return not metadata.get('messaging_handoff') or bool(metadata.get('messaging_inbound_result')) or dict(metadata.get('decision') or {}).get('resolution') == 'replay_completed'

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
