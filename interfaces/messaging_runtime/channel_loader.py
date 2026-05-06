from __future__ import annotations

from interfaces.messaging.whatsapp import build_binding as build_whatsapp_binding
from interfaces.messaging.sms import build_binding as build_sms_binding
from interfaces.messaging.email import build_binding as build_email_binding
from interfaces.messaging.messenger import build_binding as build_messenger_binding
from interfaces.regional.viber import build_binding as build_viber_binding
from interfaces.regional.line import build_binding as build_line_binding
from interfaces.regional.wechat import build_binding as build_wechat_binding
from interfaces.regional.kakaotalk import build_binding as build_kakaotalk_binding
from interfaces.telegram.runtime_binding import build_binding as build_telegram_binding
from interfaces.web.chat_widget.runtime_binding import build_binding as build_webchat_binding
from interfaces.web.api_gateway import build_binding as build_api_gateway_binding

from interfaces.messaging_runtime.channel_aliases import canonical_channel_name


BINDING_BUILDERS = {
    "telegram": build_telegram_binding,
    "whatsapp": build_whatsapp_binding,
    "sms": build_sms_binding,
    "email": build_email_binding,
    "messenger": build_messenger_binding,
    "viber": build_viber_binding,
    "line": build_line_binding,
    "wechat": build_wechat_binding,
    "kakaotalk": build_kakaotalk_binding,
    "webchat": build_webchat_binding,
    "api_gateway": build_api_gateway_binding,
}


def load_bindings(*, enabled_channels: tuple[str, ...], senders: dict[str, object] | None = None):
    senders = dict(senders or {})
    bindings = []
    for raw_channel in enabled_channels:
        channel = canonical_channel_name(raw_channel)
        try:
            builder = BINDING_BUILDERS[channel]
        except KeyError as exc:
            raise RuntimeError(f"binding builder not configured for channel: {raw_channel}") from exc
        sender = senders.get(raw_channel)
        if sender is None:
            sender = senders.get(channel)
        bindings.append(builder(sender=sender))
    return tuple(bindings)
