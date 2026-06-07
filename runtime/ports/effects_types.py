from __future__ import annotations

from typing import Any, Optional

EffectPayload = dict[str, Any] | None

__all__ = ["Any", "Dict", "Optional", "EffectPayload"]

# Compatibility aliases for legacy project-internal public imports.
# Keep these until dependent modules stop importing typing-era names from this surface.
Dict = dict

