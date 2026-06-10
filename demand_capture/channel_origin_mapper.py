from __future__ import annotations


class ChannelOriginMapper:
    MAP = {"google_maps": "maps", "yandex_maps": "maps", "website": "owned", "telegram": "messenger", "whatsapp": "messenger"}
    def map(self, origin: str) -> str:
        key = str(origin).strip().lower()
        return self.MAP.get(key, key or "unknown")
