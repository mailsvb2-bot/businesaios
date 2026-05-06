from __future__ import annotations


class ActionValidator:
    """Canonical core-owned validator for runtime application surface."""

    def valid(self, action: object) -> bool:
        return action is not None


__all__ = ["ActionValidator"]
