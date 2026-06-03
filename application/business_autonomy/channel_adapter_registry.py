from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from application.business_autonomy.channel_contracts import ChannelIdentity, TypedChannelAdapter


@dataclass(frozen=True)
class ResolvedChannelAdapter:
    identity: ChannelIdentity
    adapter: TypedChannelAdapter


class TypedChannelAdapterRegistry:
    def __init__(self, adapters: Iterable[TypedChannelAdapter] | None = None) -> None:
        self._by_kind: dict[tuple[str, str], TypedChannelAdapter] = {}
        if adapters is not None:
            self.register_many(adapters)

    def register(self, adapter: TypedChannelAdapter) -> None:
        key = (adapter.channel_kind.value, str(adapter.adapter_key).strip())
        if not key[1]:
            raise ValueError("adapter_key is required")
        if key in self._by_kind:
            raise ValueError(f"channel adapter already registered: {key[0]}:{key[1]}")
        self._by_kind[key] = adapter

    def register_many(self, adapters) -> None:
        """Register a batch through the same guarded single-adapter contract."""
        for adapter in adapters:
            self.register(adapter)

    def resolve(self, identity: ChannelIdentity) -> ResolvedChannelAdapter:
        identity.validate()
        key = (identity.channel_kind.value, str(identity.adapter_key).strip())
        try:
            adapter = self._by_kind[key]
        except KeyError as exc:
            raise KeyError(f"channel adapter not registered: {identity.channel_kind.value}:{identity.adapter_key}") from exc
        return ResolvedChannelAdapter(identity=identity, adapter=adapter)


__all__ = ["ResolvedChannelAdapter", "TypedChannelAdapterRegistry"]
