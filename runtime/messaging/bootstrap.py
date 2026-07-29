from __future__ import annotations

from interfaces.messaging.channel_common import (
    make_channel_adapter,
    make_channel_runner,
)
from interfaces.web.api_gateway import Adapter as APIGatewayAdapter
from interfaces.web.chat_widget.adapter import Adapter as WebChatAdapter
from runtime.messaging import CHANNEL_SPECS
from runtime.messaging.dispatcher import MultiChannelDispatcher

_SPECIAL_ADAPTER_FACTORIES = {
    "web_chat": WebChatAdapter,
    "api": APIGatewayAdapter,
}
_PROVIDER_TRANSPORT_KINDS = frozenset({"provider_webhook", "smtp"})


def _build_provider_adapter(channel: str):
    spec = CHANNEL_SPECS[channel]
    runner_type = make_channel_runner(
        provider=spec.key,
        env_prefix=spec.provider_env_prefix,
        default_mode=spec.mode_default,
    )
    adapter_type = make_channel_adapter(runner_factory=runner_type)
    return adapter_type()


def build_multichannel_dispatcher() -> MultiChannelDispatcher:
    adapters = {}
    for channel, spec in CHANNEL_SPECS.items():
        if spec.transport_kind == "bot_api":
            continue
        special_factory = _SPECIAL_ADAPTER_FACTORIES.get(channel)
        if special_factory is not None:
            adapters[channel] = special_factory()
            continue
        if spec.transport_kind not in _PROVIDER_TRANSPORT_KINDS:
            raise RuntimeError(
                f"messaging adapter factory missing for {channel}: "
                f"{spec.transport_kind}"
            )
        adapters[channel] = _build_provider_adapter(channel)
    return MultiChannelDispatcher(adapters=adapters)


__all__ = ["build_multichannel_dispatcher"]
