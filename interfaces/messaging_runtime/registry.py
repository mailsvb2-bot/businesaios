from __future__ import annotations


class ChannelRegistry:
    """Canonical runtime channel registry.

    Supports both legacy register(name, adapter) and current register(binding)
    forms to avoid parallel registries.
    """

    def __init__(self) -> None:
        self._channels: dict[str, object] = {}

    def register(self, name_or_binding, adapter=None) -> None:
        if adapter is None:
            binding = name_or_binding
            key = str(getattr(binding, "channel", "") or "").strip()
            value = binding
        else:
            key = str(name_or_binding or "").strip()
            value = adapter
        if not key:
            raise RuntimeError("channel name required")
        if key in self._channels:
            raise RuntimeError(f"duplicate channel binding: {key}")
        self._channels[key] = value

    def get(self, name: str):
        key = str(name or "").strip()
        try:
            return self._channels[key]
        except KeyError as exc:
            raise RuntimeError(f"unknown channel binding: {key}") from exc

    def channels(self) -> tuple[str, ...]:
        return tuple(sorted(self._channels.keys()))

    def names(self) -> tuple[str, ...]:
        return self.channels()
