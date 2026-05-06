from __future__ import annotations

SEALED_EFFECT_PREFIXES: tuple[str, ...] = ("runtime._internal",)

FORBIDDEN_EXTERNAL_EFFECT_LIBRARIES: tuple[str, ...] = (
    "requests",
    "httpx",
    "aiohttp",
    "socket",
    "urllib",
    "grpc",
)

EFFECT_LITERAL_MARKERS: tuple[str, ...] = (
    "http://",
    "https://",
    "api." "telegram.org",
    "authorization",
    "bearer ",
    "api_key",
    "token",
)

__all__ = [
    "SEALED_EFFECT_PREFIXES",
    "FORBIDDEN_EXTERNAL_EFFECT_LIBRARIES",
    "EFFECT_LITERAL_MARKERS",
]
