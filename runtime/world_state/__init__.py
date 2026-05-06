from __future__ import annotations

from runtime.lazy_namespace import build_owner_namespace

__getattr__, __dir__, __all__ = build_owner_namespace(__name__, "runtime.world_state._surface", install_public_api=True)
