from __future__ import annotations

FORBIDDEN_IMPORT_PATTERNS = (
    "platform.optimization",
    "platform.policy",
    "platform.serving",
)

__all__ = [
    "FORBIDDEN_IMPORT_PATTERNS",
]
