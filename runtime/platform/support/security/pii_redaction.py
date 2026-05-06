from __future__ import annotations

from typing import Any


class PIIRedaction:
    def redact(self, payload: dict[str, Any]) -> dict[str, Any]:
        redacted = dict(payload)
        for key in ("email", "phone", "ssn"):
            if key in redacted:
                redacted[key] = "***REDACTED***"
        return redacted

__all__ = [
    "PIIRedaction",
]
