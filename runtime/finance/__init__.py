from __future__ import annotations

from runtime.public_api_alias import install_public_api_alias
from runtime.lazy_namespace import build_owner_namespace

__getattr__, __dir__, __all__ = build_owner_namespace(__name__, "runtime.finance._surface")

install_public_api_alias(__name__)
