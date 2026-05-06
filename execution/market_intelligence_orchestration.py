from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from execution.market_intelligence_schedule_store import PersistentMarketIntelligenceScheduleStore


CANON_MARKET_INTELLIGENCE_ORCHESTRATION = True


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class SyncSchedule:
    provider: str
    source_family: str
    cadence_minutes: int
    priority: int = 100
    cooldown_minutes: int = 10
    seasonal_window_tags: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    backfill_enabled: bool = True
    catch_up_enabled: bool = True
    query: str | None = None
    subject_url: str | None = None
    region: str | None = None
    locale: str | None = None
    limit: int = 25
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketIntelligenceOrchestration:
    schedules: dict[str, SyncSchedule] = field(default_factory=dict)
    last_run_at: dict[str, str] = field(default_factory=dict)
    store: PersistentMarketIntelligenceScheduleStore = field(default_factory=PersistentMarketIntelligenceScheduleStore)
    _registered_this_process: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        persisted = self.store.load_last_run_at()
        if persisted:
            self.last_run_at.update(persisted)

    def register(self, name: str, schedule: SyncSchedule) -> None:
        normalized_name = str(name)
        self.schedules[normalized_name] = schedule
        self._registered_this_process.add(normalized_name)

    def due_runs(self, *, active_campaign_tags: tuple[str, ...] = ()) -> list[dict[str, Any]]:
        now = _utc_now()
        due: list[dict[str, Any]] = []
        for name, schedule in self.schedules.items():
            last = self._parse_dt(self.last_run_at.get(name))
            startup_catch_up = bool(schedule.catch_up_enabled) and name in self._registered_this_process
            if not startup_catch_up and last is not None and now < last + timedelta(minutes=schedule.cooldown_minutes):
                continue
            if not startup_catch_up and last is not None and now < last + timedelta(minutes=schedule.cadence_minutes):
                continue
            if schedule.seasonal_window_tags and not (set(schedule.seasonal_window_tags) & set(active_campaign_tags)):
                continue
            dependency_blocked = any(dep not in self.last_run_at for dep in schedule.dependencies)
            if dependency_blocked:
                continue
            due.append(
                {
                    'name': name,
                    'provider': schedule.provider,
                    'source_family': schedule.source_family,
                    'priority': schedule.priority,
                    'dependencies': list(schedule.dependencies),
                    'backfill_enabled': schedule.backfill_enabled,
                    'catch_up_enabled': schedule.catch_up_enabled,
                    'query': schedule.query,
                    'subject_url': schedule.subject_url,
                    'region': schedule.region,
                    'locale': schedule.locale,
                    'limit': schedule.limit,
                    'metadata': dict(schedule.metadata),
                }
            )
        return sorted(due, key=lambda row: int(row['priority']))

    def mark_run(self, name: str) -> None:
        self.last_run_at[name] = _utc_now().isoformat()
        self._registered_this_process.discard(str(name))
        self.store.save_last_run_at(self.last_run_at)

    def snapshot(self) -> dict[str, Any]:
        return {
            'schedules': {
                str(name): {
                    'provider': schedule.provider,
                    'source_family': schedule.source_family,
                    'cadence_minutes': schedule.cadence_minutes,
                    'priority': schedule.priority,
                    'cooldown_minutes': schedule.cooldown_minutes,
                    'dependencies': list(schedule.dependencies),
                    'backfill_enabled': schedule.backfill_enabled,
                    'catch_up_enabled': schedule.catch_up_enabled,
                    'query': schedule.query,
                    'subject_url': schedule.subject_url,
                    'region': schedule.region,
                    'locale': schedule.locale,
                    'limit': schedule.limit,
                    'metadata': dict(schedule.metadata),
                }
                for name, schedule in self.schedules.items()
            },
            'last_run_at': dict(self.last_run_at),
        }

    def _parse_dt(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
