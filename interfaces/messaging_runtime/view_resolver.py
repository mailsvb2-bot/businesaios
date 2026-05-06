from __future__ import annotations

from .contracts import OutboundEnvelope, ViewModel
from .views_policy import ChannelViewsPolicy


class ChannelAwareViewResolver:
    def __init__(self, policy: ChannelViewsPolicy | None = None) -> None:
        self._policy = policy or ChannelViewsPolicy()

    def resolve(self, view: ViewModel) -> OutboundEnvelope:
        rendered = self._policy.render(
            channel=view.channel,
            body=view.body,
            metadata=view.metadata,
        )
        envelope = OutboundEnvelope(
            channel=view.channel,
            user_id=view.user_id,
            correlation_id=view.correlation_id,
            body=rendered.body,
            dedupe_key=f"{view.channel}:{view.user_id}:{view.correlation_id}",
            metadata=rendered.metadata,
        )
        envelope.validate()
        return envelope
