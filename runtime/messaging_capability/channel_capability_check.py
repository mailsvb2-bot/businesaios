from __future__ import annotations

from interfaces.messaging_runtime.capabilities import get_capabilities
from runtime.messaging.channel_normalizer import normalize_channel

_REQUIRED_FIELDS = (
    "plain_text",
    "html",
    "buttons",
    "attachments",
    "structured_payload",
    "subject_line",
)


def channel_supports_requirement(*, channel: str, requirement) -> bool:
    capabilities = get_capabilities(normalize_channel(channel))
    for field in _REQUIRED_FIELDS:
        if bool(getattr(requirement, field)) and not bool(getattr(capabilities, field)):
            return False
    return True
