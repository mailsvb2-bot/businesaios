from __future__ import annotations

from typing import Any


def is_duplicate(*, seen_updates: Any, update_id: int) -> bool:
    return bool(seen_updates.seen(f"upd:{int(update_id)}"))
