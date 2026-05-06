from __future__ import annotations

"""Canonical product domain namespace.

Use ``core.product`` for live product-planning logic. Historical
``core.products`` imports remain compatibility-only and must not become a second
active domain surface.
"""

CANON_PRODUCT_DOMAIN = True

from core.product.contracts import *  # noqa: F401,F403
from core.product.enums import *  # noqa: F401,F403
from core.product.errors import *  # noqa: F401,F403
from core.product.guard import *  # noqa: F401,F403
from core.product.policy import *  # noqa: F401,F403
from core.product.service import *  # noqa: F401,F403

__all__ = [name for name in globals() if not name.startswith("_")]
