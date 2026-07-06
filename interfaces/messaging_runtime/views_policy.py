from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .capabilities import ChannelCapabilities, get_capabilities


@dataclass(frozen=True)
class RenderedPayload:
    channel: str
    body: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ChannelViewsPolicy:
    def render(self, *, channel: str, body: str, metadata: Mapping[str, Any] | None = None) -> RenderedPayload:
        caps = get_capabilities(channel)
        meta = dict(metadata or {})
        return RenderedPayload(
            channel=channel,
            body=self._sanitize_body(caps, body),
            metadata=self._sanitize_metadata(caps, meta),
        )

    def _sanitize_body(self, caps: ChannelCapabilities, body: str) -> str:
        value = str(body).strip()
        return value if caps.plain_text else str(body)

    def _sanitize_metadata(self, caps: ChannelCapabilities, metadata: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if caps.subject_line and metadata.get("subject"):
            result["subject"] = str(metadata["subject"])
        if caps.html and metadata.get("html"):
            result["html"] = str(metadata["html"])
        if caps.attachments and metadata.get("attachments"):
            result["attachments"] = list(metadata["attachments"])
        if caps.buttons and metadata.get("buttons"):
            result["buttons"] = list(metadata["buttons"])
        if caps.structured_payload and metadata.get("structured_payload"):
            result["structured_payload"] = dict(metadata["structured_payload"])
        return result
