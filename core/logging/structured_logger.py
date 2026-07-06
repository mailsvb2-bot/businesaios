from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LogEvent:
    ts_ms: int
    level: str
    msg: str
    fields: Mapping[str, Any]


class StructuredLogger:
    def __init__(self, sink) -> None:
        self._sink = sink

    def info(self, msg: str, **fields: Any) -> None:
        self._emit("INFO", msg, fields)

    def warn(self, msg: str, **fields: Any) -> None:
        self._emit("WARN", msg, fields)

    def error(self, msg: str, **fields: Any) -> None:
        self._emit("ERROR", msg, fields)

    def _emit(self, level: str, msg: str, fields: Mapping[str, Any]) -> None:
        ev = LogEvent(ts_ms=int(time.time() * 1000), level=level, msg=msg, fields=dict(fields))
        self._sink.write(json.dumps({"ts_ms": ev.ts_ms, "level": ev.level, "msg": ev.msg, **ev.fields}) + "\n")
