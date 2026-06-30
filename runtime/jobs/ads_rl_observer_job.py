"""Worker job: Ads RL automatic observe/tick.

Usage example (pseudo):

  from runtime.entrypoints.telegram_longpoll import build_system
  from runtime.jobs.ads_rl_observer_job import run_once
  system = build_system()
  run_once(system=system, tenant_id="t1")

This job is intentionally NOT started automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from runtime.ads import ObserveTickResult, observe_tick_once

@dataclass(frozen=True)
class JobDeps:
    event_store: Any
    ads_rl_service: Any


def run_once(*, deps: JobDeps, tenant_id: str, max_import_events: int = 500) -> ObserveTickResult:
    return observe_tick_once(
        tenant_id=str(tenant_id),
        event_store=deps.event_store,
        rl_service=deps.ads_rl_service,
        max_import_events=int(max_import_events),
    )
