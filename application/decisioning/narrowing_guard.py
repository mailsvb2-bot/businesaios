from __future__ import annotations

from typing import Sequence, Any

def detect_hidden_choice(values: Sequence[Any]) -> bool:
    """Detect suspicious patterns like single-element narrowing."""
    try:
        return len(values) == 1
    except Exception:
        return False
