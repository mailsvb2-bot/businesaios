from __future__ import annotations

import html


def esc(value) -> str:
    return html.escape(str(value or ""))


__all__ = ["esc"]
