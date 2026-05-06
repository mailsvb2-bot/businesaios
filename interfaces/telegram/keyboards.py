"""Compatibility re-export.

The canonical keyboard definitions live in core.ux.telegram_keyboards
to avoid core->interfaces dependency.
"""

from core.ux.telegram_keyboards import kb_back_main, kb_demo_kind, kb_main

__all__ = ["kb_main", "kb_back_main", "kb_demo_kind"]
