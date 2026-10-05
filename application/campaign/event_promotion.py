from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, urlencode, urlsplit


@dataclass(frozen=True, slots=True)
class EventPromotionTarget:
    event_id: str
    public_slug: str
    public_base_url: str

    def __post_init__(self) -> None:
        event_id = str(self.event_id or "").strip()
        slug = str(self.public_slug or "").strip()
        base = str(self.public_base_url or "").strip().rstrip("/")
        parsed = urlsplit(base)
        if not event_id or len(event_id) > 200:
            raise ValueError("event_id is required")
        if not slug or len(slug) > 240:
            raise ValueError("public event slug is required")
        if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment:
            raise ValueError("public event base URL must be a clean HTTPS origin/path")
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "public_slug", slug)
        object.__setattr__(self, "public_base_url", base)


def event_advertising_url(target: EventPromotionTarget) -> str:
    query = urlencode({"source": "ads", "campaign_ref": f"event:{target.event_id}"})
    return f"{target.public_base_url}/e/{quote(target.public_slug, safe='')}?{query}"


__all__ = ["EventPromotionTarget", "event_advertising_url"]
