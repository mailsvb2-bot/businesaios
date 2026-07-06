from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_MAX_PAYLOAD_KEYS = 12


class PlatformSupportUnavailableAdapterError(NotImplementedError):
    """Raised when a platform-support adapter is declared but not wired to a live integration."""


def _normalized_surface_name(value: str, *, field_name: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise ValueError(f"{field_name} must not be empty")
    return token


def _payload_keys(payload: Mapping[str, Any] | None) -> tuple[str, ...]:
    if payload is None:
        return ()
    return tuple(sorted(str(key) for key in payload)[:_MAX_PAYLOAD_KEYS])


def build_unavailable_adapter_message(*, adapter_name: str, operation: str, payload: Mapping[str, Any] | None = None) -> str:
    adapter = _normalized_surface_name(adapter_name, field_name="adapter_name")
    operation_name = _normalized_surface_name(operation, field_name="operation")
    payload_keys = list(_payload_keys(payload))
    return (
        f"{adapter}.{operation_name} is declared but not wired to a live integration; "
        f"payload_keys={payload_keys}"
    )


def raise_unavailable_adapter(*, adapter_name: str, operation: str, payload: Mapping[str, Any] | None = None) -> None:
    raise PlatformSupportUnavailableAdapterError(
        build_unavailable_adapter_message(adapter_name=adapter_name, operation=operation, payload=payload)
    )


__all__ = [
    "PlatformSupportUnavailableAdapterError",
    "build_unavailable_adapter_message",
    "raise_unavailable_adapter",
]
