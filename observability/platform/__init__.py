"""Platform-layer observability facade.

This namespace is for storage/export-adjacent helpers and persistence-friendly
paths. It must stay free from sovereign decision logic.
"""

from __future__ import annotations

from canon.public_api_alias import install_public_api_alias

from observability.platform.observability import CANON_PLATFORM_OBSERVABILITY_PUBLIC_API, swallow

__all__ = ["CANON_PLATFORM_OBSERVABILITY_PUBLIC_API", "swallow"]


def __getattr__(name: str):
    if name in __all__:
        return globals()[name]
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))



install_public_api_alias(__name__)
