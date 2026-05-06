"""Platform-layer observability helpers.

This namespace is for storage/export-adjacent helpers and must stay free from
sovereign decision logic.
"""

from __future__ import annotations

from canon.public_api_alias import install_public_api_alias

from observability.platform.observability.silent import swallow

CANON_PLATFORM_OBSERVABILITY_PUBLIC_API = True

__all__ = ["CANON_PLATFORM_OBSERVABILITY_PUBLIC_API", "swallow"]


install_public_api_alias(__name__)
