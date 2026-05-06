from __future__ import annotations

"""Canonical lightweight web package surface.

The root package exposes stable public names without importing the full web
runtime during package import. This preserves the public API while keeping
startup/import smoke deterministic.
"""

from importlib import import_module
from typing import Any

try:
    from runtime.public_api_alias import install_public_api_alias
except Exception:  # pragma: no cover - import-time compatibility guard
    install_public_api_alias = None  # type: ignore[assignment]

if install_public_api_alias is not None:
    install_public_api_alias(__name__)

_CANONICAL_EXPORTS: dict[str, tuple[str, str]] = {
    "WebApp": ("app.web.app", "WebApp"),
    "AuthService": ("app.web.auth", "AuthService"),
    "Routes": ("app.web.routes", "Routes"),
    "SessionStore": ("app.web.session", "SessionStore"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _CANONICAL_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_CANONICAL_EXPORTS))


__all__ = sorted(_CANONICAL_EXPORTS)
