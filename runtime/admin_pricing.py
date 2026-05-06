from __future__ import annotations

from runtime.lazy_namespace import build_owner_namespace

__getattr__, __dir__, __all__ = build_owner_namespace(
    __name__,
    "runtime._internal.effects_domains.admin_pricing",
)
