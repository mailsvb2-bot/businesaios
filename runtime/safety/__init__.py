from __future__ import annotations

from runtime.lazy_namespace import build_owner_namespace
from runtime.public_api_alias import install_public_api_alias

__getattr__, __dir__, __all__ = build_owner_namespace(__name__, "runtime.safety._surface")

install_public_api_alias(__name__)
