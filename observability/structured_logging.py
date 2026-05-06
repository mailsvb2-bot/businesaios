from __future__ import annotations

"""Compatibility facade for structured logging.

CANON_COMPAT_SHIM = True

Keeps legacy infra imports alive while delegating implementation to the
canonical core observability package. No business logic lives here.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from core.observability.structured_logging import bind, clear, configure_structured_logging


@dataclass
class StructuredLogger:
    name: str
    _logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._logger = logging.getLogger(self.name)

    def _emit(self, level: str, event: str, **fields: Any) -> None:
        bind(**fields)
        try:
            getattr(self._logger, level)(str(event))
        finally:
            clear()

    def info(self, event: str, **fields: Any) -> None:
        self._emit("info", event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._emit("warning", event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self._emit("error", event, **fields)

    def exception(self, event: str, **fields: Any) -> None:
        self._emit("exception", event, **fields)


__all__ = ["StructuredLogger", "bind", "clear", "configure_structured_logging"]
