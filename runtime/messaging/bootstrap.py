from __future__ import annotations

from interfaces.messaging.channel_common import (
    make_channel_adapter,
    make_channel_runner,
)
from interfaces.web.api_gateway import Adapter as APIGatewayAdapter
from interfaces.web.chat_widget.adapter import Adapter as WebChatAdapter
from runtime.business_autonomy.provider_payload_normalizers import ProviderPayloadNormalizers
from runtime.messaging import CHANNEL_SPECS
from runtime.messaging.delivery_result import DeliveryResult
from runtime.messaging.dispatcher import MultiChannelDispatcher

_SPECIAL_ADAPTER_FACTORIES = {
    "web_chat": WebChatAdapter,
    "api": APIGatewayAdapter,
}
_PROVIDER_TRANSPORT_KINDS = frozenset({"provider_webhook", "smtp"})
_NATIVE_QUEUE_PROVIDERS = {"vk": "vk_messaging", "max": "max_messaging"}
def _build_provider_adapter(channel: str):
    spec = CHANNEL_SPECS[channel]
    runner_type = make_channel_runner(
        provider=spec.key,
        env_prefix=spec.provider_env_prefix,
        default_mode=spec.mode_default,
    )
    adapter_type = make_channel_adapter(runner_factory=runner_type)
    return adapter_type()

class _NativeProviderQueueAdapter:
    def __init__(self, channel: str, service_factory=None) -> None:
        self.channel, self.provider_key = str(channel), _NATIVE_QUEUE_PROVIDERS[str(channel)]
        self._service_factory, self._cached_service = service_factory, None
    def _service(self):
        if self._cached_service is None:
            if self._service_factory is None:
                from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service
                self._service_factory = build_business_autonomy_guarded_service
            service = self._service_factory()
            self._cached_service = getattr(service, "_provider_admin_service", service)
        return self._cached_service
    def send(self, msg) -> DeliveryResult:
        context = dict((msg.track_payload or {}).get("_provider_native") or {}) if isinstance(msg.track_payload, dict) else {}
        business_id = str(context.get("business_id") or "").strip()
        if not business_id:
            return DeliveryResult(False, self.channel, "blocked", "", {"provider": self.provider_key, "reason": "native_business_id_required"})
        service = self._service()
        payload = ProviderPayloadNormalizers().normalize_outbound(provider=service.provider_registry.get(self.provider_key), operation="message_send", payload={"user_id": msg.user_id, "text": msg.text, **{key: context[key] for key in ("peer_id", "chat_id", "random_id") if key in context}})
        payload["_approval"] = {"decision_id": str(msg.decision_id), "execution_id": str(msg.decision_id), **({"approval_id": str(context["approval_id"])} if context.get("approval_id") else {})}
        outcome = service.execute_queued_provider_sync(tenant_id=msg.tenant_id, business_id=business_id, provider_key=self.provider_key, operation="message_send", mode="live", payload=payload, worker_id="provider-messaging-effect")
        dispatch, result = dict(outcome.get("dispatch") or {}), outcome.get("result")
        if not bool(dispatch.get("queued")):
            guard = dict(dict(dispatch.get("metadata") or {}).get("provider_write_guard") or {})
            approval = dict(dict(guard.get("metadata") or {}).get("approval") or {})
            detail = {"provider": self.provider_key, "reason": str(approval.get("reason") or guard.get("reason") or dispatch.get("status") or "provider_write_blocked"), "approval_id": approval.get("approval_id"), "approval_required": bool(approval.get("approval_required")), "job_id": dispatch.get("job_id")}
            return DeliveryResult(False, self.channel, "approval_required" if approval.get("approval_id") else "blocked", "", detail)
        if not isinstance(result, dict):
            return DeliveryResult(False, self.channel, "in_progress", "", {"provider": self.provider_key, "reason": "provider_queue_result_pending", "job_id": dispatch.get("job_id")})
        if bool(result.get("accepted")) and str(result.get("status")) == "live_executed" and (external_id := str(dict(result.get("parsed_response") or {}).get("resource_id") or "").strip()):
            return DeliveryResult(True, self.channel, "accepted", external_id, {"provider": self.provider_key, "accepted": True, "delivered": False, "job_id": dispatch.get("job_id"), "provider_status": result.get("status")})
        reason = "provider_receipt_missing" if bool(result.get("accepted")) else str(dict(result.get("error") or {}).get("category") or result.get("status") or "provider_send_failed")
        return DeliveryResult(False, self.channel, "failed", "", {"provider": self.provider_key, "reason": reason, "job_id": dispatch.get("job_id"), "provider_status": result.get("status")})


def build_multichannel_dispatcher() -> MultiChannelDispatcher:
    adapters = {}
    for channel, spec in CHANNEL_SPECS.items():
        if spec.transport_kind == "bot_api":
            continue
        special_factory = _SPECIAL_ADAPTER_FACTORIES.get(channel)
        if special_factory is not None:
            adapters[channel] = special_factory()
            continue
        if channel in _NATIVE_QUEUE_PROVIDERS:
            adapters[channel] = _NativeProviderQueueAdapter(channel)
            continue
        if spec.transport_kind not in _PROVIDER_TRANSPORT_KINDS:
            raise RuntimeError(
                f"messaging adapter factory missing for {channel}: "
                f"{spec.transport_kind}"
            )
        adapters[channel] = _build_provider_adapter(channel)
    return MultiChannelDispatcher(adapters=adapters)


__all__ = ["_NativeProviderQueueAdapter", "build_multichannel_dispatcher"]
