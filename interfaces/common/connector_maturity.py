from __future__ import annotations

from enum import Enum


class ConnectorMaturity(str, Enum):
    REAL = "real"
    CAPABILITY_SHELL = "capability_shell"
    PLACEHOLDER = "placeholder"


__all__ = ["ConnectorMaturity"]
