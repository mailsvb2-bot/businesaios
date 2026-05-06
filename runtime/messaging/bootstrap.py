from __future__ import annotations

from interfaces.messaging.email import Adapter as EmailAdapter
from interfaces.messaging.instagram import Adapter as InstagramAdapter
from interfaces.messaging.messenger import Adapter as MessengerAdapter
from interfaces.messaging.sms import Adapter as SMSAdapter
from interfaces.messaging.whatsapp import Adapter as WhatsAppAdapter
from interfaces.regional.kakaotalk import Adapter as KakaoTalkAdapter
from interfaces.regional.line import Adapter as LineAdapter
from interfaces.regional.viber import Adapter as ViberAdapter
from interfaces.regional.wechat import Adapter as WeChatAdapter
from interfaces.web.api_gateway import Adapter as APIGatewayAdapter
from interfaces.web.chat_widget.adapter import Adapter as WebChatAdapter
from runtime.messaging.dispatcher import MultiChannelDispatcher


def build_multichannel_dispatcher() -> MultiChannelDispatcher:
    return MultiChannelDispatcher(
        adapters={
            "whatsapp": WhatsAppAdapter(),
            "sms": SMSAdapter(),
            "email": EmailAdapter(),
            "instagram": InstagramAdapter(),
            "messenger": MessengerAdapter(),
            "web_chat": WebChatAdapter(),
            "api": APIGatewayAdapter(),
            "line": LineAdapter(),
            "wechat": WeChatAdapter(),
            "kakaotalk": KakaoTalkAdapter(),
            "viber": ViberAdapter(),
        }
    )
