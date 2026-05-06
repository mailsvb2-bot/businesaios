from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol

@dataclass(frozen=True)
class SignalMemoryRecord:
    kind: str
    name: str
    last_value: str
    count: int
    last_seen_run_id: str | None = None
    last_seen_at: str | None = None
    trend: str = "unknown"
    def key(self) -> str:
        return f"{self.kind}::{self.name}"

@dataclass(frozen=True)
class PatternEvidence:
    key: str
    count: int
    last_seen_run_id: str | None = None
    last_seen_at: str | None = None
    confidence: float = 0.0
    frequency: float = 0.0
    freshness: float = 0.0
    source_run_ids: tuple[str, ...] = ()

@dataclass(frozen=True)
class BusinessMemoryRunRecord:
    run_id: str
    goal: str
    completed: bool
    stop_reason: str
    goal_score: float
    step_count: int
    summary: str
    channel: str
    region: str
    product_name: str
    goal_family: str = "general"
    fingerprint: dict[str, str] = field(default_factory=dict)
    recorded_at: str | None = None

@dataclass(frozen=True)
class AntiPatternRecord:
    key: str
    confidence: float
    frequency: float
    freshness: float
    source_run_ids: tuple[str, ...] = ()
    reason: str = ""

@dataclass(frozen=True)
class MemoryTrendSnapshot:
    window_size: int
    goal_score_trend: str
    failure_trend: str
    win_trend: str
    signal_trend: str
    average_goal_score_window: float
    failure_rate_window: float
    win_rate_window: float

class BusinessOperatingMemoryLike(Protocol):
    recent_runs: tuple[BusinessMemoryRunRecord, ...]
