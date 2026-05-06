from __future__ import annotations

from collections import deque

ROLLING_CK_TO_BTN: dict[str, str] = {}
ROLLING_BTN_TOTALS: dict[str, deque[int]] = {}
ROLLING_MAX_SAMPLES: int = 4000
LAST_WATCHDOG_MS: int = 0
LAST_EMITTED_OFFENDERS: str = ""
RECENT_SLA_BREACHES: deque[dict] = deque(maxlen=5)
