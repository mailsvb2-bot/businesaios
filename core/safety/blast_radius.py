from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from core.observability.errors import log_exception_throttled

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BlastRadiusPolicy:
    """Simple blast radius limiter per action."""

    max_per_hour: int = 0


def _now_ms() -> int:
    return int(time.time() * 1000)


def count_recent_actions(*, event_log: Any, tenant_id: str, action: str, window_ms: int) -> int:
    try:
        since = _now_ms() - int(window_ms)
        if hasattr(event_log, "query_recent"):
            evs = event_log.query_recent(
                event_type="decision_executed",
                since_ms=since,
                filters={"tenant_id": str(tenant_id), "action": str(action)},
            )
            return int(len(list(evs or [])))
    except Exception as exc:
        log_exception_throttled(log, "blast_radius_query_recent_failed", exc)
    return 0


def allow_action(*, policy: BlastRadiusPolicy, event_log: Any, tenant_id: str, action: str) -> Tuple[bool, Dict[str, Any]]:
    if int(policy.max_per_hour or 0) <= 0:
        return True, {"max_per_hour": int(policy.max_per_hour or 0)}

    cnt = count_recent_actions(event_log=event_log, tenant_id=tenant_id, action=action, window_ms=60 * 60 * 1000)
    ok = cnt < int(policy.max_per_hour)
    return bool(ok), {"count_last_hour": int(cnt), "max_per_hour": int(policy.max_per_hour)}
