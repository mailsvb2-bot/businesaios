from __future__ import annotations

"""Backward-compat re-export.

Historically keyboard primitives lived under policies.
Offers and other layers may also need them; canonical location is core.ux.
"""

from core.ux.inline_keyboards import inline_button, inline_keyboard

__all__ = ["inline_button", "inline_keyboard"]
