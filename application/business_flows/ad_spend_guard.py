"""Fail-closed ad spend guard (port of clientplatform ad_spend_runtime + ad_spend_control guard).

Pure decision logic over an owner authorization and a READ-ONLY provider budget snapshot.
Nothing here mutates a provider or spends money: a sweep only yields ``ad_spend_stop_queued``
facts (dry-run stop requests) that the executor records; live provider stop/launch stays
behind ``ad_proposals.publish_decision`` (production_ready=False -> blocked).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REPORT_TZ_ENV = "YANDEX_DIRECT_REPORT_TIMEZONE"
SNAPSHOT_VALIDITY = timedelta(seconds=30)
MANAGED_PREFIX = "bai-managed:"
AUTH_ERRORS = frozenset(
    {"provider_http_401", "provider_53", "provider_54", "provider_55", "provider_56",
     "provider_invalid_token", "provider_unauthorized", "oauth_refresh_token_missing"}
)
LIVE_STATUSES = frozenset({"authorized", "launching", "active"})


class SpendInvariantViolation(RuntimeError):
    pass


class ProviderReadError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Snapshot:
    connection_id: str
    external_account_id: str
    external_campaign_id: str
    currency: str
    spent_today_minor: int
    strategy: str
    captured_at: datetime
    launch_eligible: bool = True
    report_date: str = ""


@dataclass(frozen=True)
class Authorization:
    authorization_id: str
    business_id: str
    connection_id: str
    external_campaign_id: str
    currency: str
    hard_cap_minor: int
    daily_cap_minor: int
    expires_at: datetime
    status: str
    consent: Snapshot  # provider snapshot captured at owner consent


@dataclass(frozen=True)
class GuardVerdict:
    allowed: bool
    reason: str | None = None


@dataclass
class SweepResult:
    scanned: int = 0
    allowed: int = 0
    stops_queued: int = 0
    failed_closed: int = 0
    facts: list[dict[str, Any]] = field(default_factory=list)


def ts(value: datetime | str | None = None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return parsed.astimezone(UTC)


def report_timezone(env: dict[str, str] | None = None) -> ZoneInfo:
    raw = str((env if env is not None else os.environ).get(REPORT_TZ_ENV) or "").strip()
    if not raw:
        raise SpendInvariantViolation(f"{REPORT_TZ_ENV} is required for daily spend limits")
    try:
        return ZoneInfo(raw)
    except ZoneInfoNotFoundError as exc:
        raise SpendInvariantViolation(f"{REPORT_TZ_ENV} is not a valid IANA timezone") from exc


def provider_report_date(now: datetime | str | None, tz: ZoneInfo) -> str:
    return ts(now).astimezone(tz).date().isoformat()


def managed_strategy(hard_cap_minor: int, daily_cap_minor: int) -> str:
    weekly = min(int(hard_cap_minor), int(daily_cap_minor) * 7)
    return f"{MANAGED_PREFIX}weekly={weekly * 10_000}"  # minor units -> micros


def strategy_matches(consented: str, current: str, *, hard_cap_minor: int, daily_cap_minor: int, require_applied: bool) -> bool:
    consented, current = str(consented or "").strip(), str(current or "").strip()
    if not consented.startswith(MANAGED_PREFIX):
        return True
    target = managed_strategy(hard_cap_minor, daily_cap_minor)
    return current == target if require_applied else current in {consented, target}


def guard(auth: Authorization, snap: Snapshot, total_spent_minor: int, now: datetime | str | None = None) -> GuardVerdict:
    """Port of ad_spend_control.evaluate_ad_spend_guard (order preserved)."""
    t = ts(now)
    if auth.status == "revoked":
        return GuardVerdict(False, "revoked")
    if t >= ts(auth.expires_at):
        return GuardVerdict(False, "expired")
    if t - ts(snap.captured_at) > SNAPSHOT_VALIDITY or ts(snap.captured_at) > t + SNAPSHOT_VALIDITY:
        return GuardVerdict(False, "snapshot_stale")
    if snap.connection_id != auth.connection_id or snap.external_campaign_id != auth.external_campaign_id:
        return GuardVerdict(False, "provider_ineligible")
    if snap.currency != auth.currency or not snap.launch_eligible:
        return GuardVerdict(False, "provider_ineligible")
    if isinstance(total_spent_minor, bool) or int(total_spent_minor) < 0:
        raise ValueError("total_spent_minor must be a non-negative integer")
    if int(total_spent_minor) >= auth.hard_cap_minor:
        return GuardVerdict(False, "hard_cap")
    if snap.spent_today_minor >= auth.daily_cap_minor:
        return GuardVerdict(False, "daily_cap")
    if auth.status not in LIVE_STATUSES:
        return GuardVerdict(False, "provider_ineligible")
    return GuardVerdict(True)


def runtime_guard(auth: Authorization, snap: Snapshot, tz: ZoneInfo, now: datetime | str | None = None) -> GuardVerdict:
    """Port of ad_spend_runtime.evaluate_runtime_spend_guard."""
    t = ts(now)
    c = auth.consent
    if snap.external_account_id != c.external_account_id:
        return GuardVerdict(False, "provider_ineligible")
    if ts(c.captured_at).astimezone(tz).date() != t.astimezone(tz).date():
        return GuardVerdict(False, "provider_ineligible")
    if snap.spent_today_minor < c.spent_today_minor:
        return GuardVerdict(False, "provider_ineligible")
    if not strategy_matches(c.strategy, snap.strategy, hard_cap_minor=auth.hard_cap_minor,
                            daily_cap_minor=auth.daily_cap_minor, require_applied=auth.status == "active"):
        return GuardVerdict(False, "provider_ineligible")
    return guard(auth, snap, snap.spent_today_minor - c.spent_today_minor, t)


Reader = Callable[[str, Authorization, str, datetime], Snapshot]  # (access_token, auth, report_date, now)


def fresh_snapshot(
    auth: Authorization,
    *,
    account_id: str,
    token: dict[str, str],
    read: Reader,
    refresh: Callable[[dict[str, str]], dict[str, str]] | None,
    tz: ZoneInfo,
    now: datetime | str | None = None,
) -> tuple[Snapshot, dict[str, str] | None]:
    """Read-only snapshot; on an auth error refreshes once. Returns (snapshot, refreshed_token|None)."""
    t = ts(now)
    if account_id != auth.consent.external_account_id:
        raise SpendInvariantViolation("advertising account changed after owner consent")
    day = provider_report_date(t, tz)
    try:
        snap, new = read(token["access_token"], auth, day, t), None
    except ProviderReadError as exc:
        if exc.code not in AUTH_ERRORS or not token.get("refresh_token") or refresh is None:
            raise
        new = refresh(token)
        snap = read(new["access_token"], auth, day, t)
    if snap.report_date and snap.report_date != day:
        raise SpendInvariantViolation("provider report date mismatch")
    return snap, new


def fail_closed(exc: BaseException) -> tuple[GuardVerdict, str]:
    code = getattr(exc, "code", "") if isinstance(exc, ProviderReadError) else type(exc).__name__.lower()
    return GuardVerdict(False, "provider_ineligible"), f"provider_guard_{code}"


def active_ids(auths: Iterable[Authorization], *, limit: int) -> list[Authorization]:
    live = [a for a in auths if a.status in {"launching", "active"}]
    return live[: max(1, min(int(limit), 500))]


def sweep(
    auths: Iterable[Authorization],
    snapshot_for: Callable[[Authorization], Snapshot],
    *,
    tz: ZoneInfo,
    limit: int = 100,
    now: datetime | str | None = None,
) -> SweepResult:
    """Port of sweep_active_ad_spend_authorizations: every failure fails closed into a dry-run stop fact."""
    t = ts(now)
    out = SweepResult()
    for a in active_ids(auths, limit=limit):
        out.scanned += 1
        try:
            if t >= ts(a.expires_at):
                d = GuardVerdict(False, "expired")
            elif a.status == "revoked":
                d = GuardVerdict(False, "revoked")
            else:
                d = runtime_guard(a, snapshot_for(a), tz, t)
            reason = d.reason or "provider_ineligible"
        except (ProviderReadError, SpendInvariantViolation, OSError, RuntimeError, ValueError) as exc:
            out.failed_closed += 1
            d, reason = fail_closed(exc)
        if d.allowed:
            out.allowed += 1
            continue
        out.stops_queued += 1
        out.facts.append({"step": "ad_spend_stop_queued", "authorization_id": a.authorization_id,
                          "business_id": a.business_id, "reason": reason, "dry_run": True, "at": t.isoformat()})
    return out
