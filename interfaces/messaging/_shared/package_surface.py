from __future__ import annotations

from types import ModuleType
from typing import Any

from interfaces.messaging._shared.inbound_normalizer import normalize_provider_inbound
from interfaces.messaging._shared.provider_runtime import map_result_for, send_raw_for
from interfaces.messaging._shared.provider_surface import make_build_config
from interfaces.messaging._shared.runner_helpers import delivery_preview, sender_identity
from interfaces.messaging.channel_common import build_channel_binding_for, make_channel_adapter, make_channel_runner

CANON_CHANNEL_PACKAGE_SURFACE = True

_CHANNEL_EXPORTS = (
    "Adapter",
    "Runner",
    "build_binding",
    "build_config",
    "delivery_preview",
    "map_result",
    "normalize_inbound",
    "send_raw",
    "sender_identity",
)


def install_channel_package_namespace(
    package: ModuleType,
    *,
    provider: str,
    env_prefix: str,
    default_mode: str,
) -> tuple[object, object, list[str]]:
    cache: dict[str, Any] = {}

    def _resolve(name: str) -> Any:
        if name in cache:
            return cache[name]
        runner = cache.setdefault(
            "Runner",
            make_channel_runner(provider=provider, env_prefix=env_prefix, default_mode=default_mode),
        )
        adapter = cache.setdefault("Adapter", make_channel_adapter(runner_factory=runner))
        build_config = cache.setdefault(
            "build_config",
            make_build_config(provider=provider, env_prefix=env_prefix, default_mode=default_mode),
        )

        def send_raw(*, cfg, msg):
            return send_raw_for(cfg=cfg, msg=msg)

        def map_result(*, msg, raw):
            return map_result_for(msg=msg, raw=raw)

        def normalize_inbound(payload):
            return normalize_provider_inbound(provider_channel=provider, payload=payload)

        def build_binding(*, sender=None):
            return build_channel_binding_for(channel=provider, sender=sender)

        resolved = {
            "Adapter": adapter,
            "Runner": runner,
            "build_binding": build_binding,
            "build_config": build_config,
            "delivery_preview": delivery_preview,
            "map_result": map_result,
            "normalize_inbound": normalize_inbound,
            "send_raw": send_raw,
            "sender_identity": sender_identity,
        }
        cache.update(resolved)
        value = resolved[name]
        setattr(package, name, value)
        return value

    def __getattr__(name: str) -> Any:
        if name not in _CHANNEL_EXPORTS:
            raise AttributeError(name)
        return _resolve(name)

    def __dir__() -> list[str]:
        return sorted(set(package.__dict__) | set(_CHANNEL_EXPORTS))

    return __getattr__, __dir__, list(_CHANNEL_EXPORTS)


__all__ = [
    "CANON_CHANNEL_PACKAGE_SURFACE",
    "install_channel_package_namespace",
]
