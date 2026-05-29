from __future__ import annotations

import contextvars
import json
import logging
import time
from typing import Any

from core.observability.errors import log_exception_throttled

log = logging.getLogger(__name__)

# Contextvars: safe across async and threads.
# For observability: bind(correlation_id=..., decision_id=...) in executor context (see runtime/execution/telemetry).
_ctx: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar("log_ctx", default={})


def bind(**fields: Any):
    cur = dict(_ctx.get() or {})
    for k, v in fields.items():
        if v is None:
            continue
        cur[str(k)] = v
    _ctx.set(cur)


def clear():
    _ctx.set({})


def snapshot() -> dict[str, Any]:
    return dict(_ctx.get() or {})


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, Any] = {
            "ts_ms": int(time.time() * 1000),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # merge context
        try:
            base.update(snapshot())
        except Exception as exc:
            log_exception_throttled(log, "structured_logging_context_merge_failed", exc)

        # exception info
        if record.exc_info:
            try:
                base["exc"] = self.formatException(record.exc_info)
            except Exception:
                base["exc"] = "EXC_FORMAT_FAILED"

        return json.dumps(base, ensure_ascii=False, separators=(",", ":"))


def configure_structured_logging(*, enabled: bool, level: str = "INFO") -> None:
    if not enabled:
        return
    root = logging.getLogger()
    try:
        root.setLevel(getattr(logging, (level or "INFO").upper(), logging.INFO))
    except Exception:
        root.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    # replace all handlers to avoid mixed formats
    root.handlers = [handler]
