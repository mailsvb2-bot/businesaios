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


# --- owner consent lifecycle + operation queue (port of ad_spend_consent / ad_spend_control /
# ad_spend_operations). Fact replay, no DB, no provider mutation: launch is gated behind
# MUTATIONS_ENV (default off) and every stop is a dry-run fact recorded by the executor.
MUTATIONS_ENV = "BAI_AD_SPEND_MUTATIONS_ENABLED"
_CONSENT_STEPS = {"ad_spend_consent_requested": "pending_consent", "ad_spend_consent_granted": "authorized",
                  "ad_spend_consent_revoked": "revoked"}


def _sha(obj: object) -> str:
    import hashlib
    import json
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def snapshot_hash(snap: Snapshot) -> str:
    return _sha([snap.connection_id, snap.external_account_id, snap.external_campaign_id, snap.currency,
                 snap.spent_today_minor, snap.strategy, ts(snap.captured_at).isoformat()])


def terms_hash(auth: Authorization) -> str:
    return _sha([auth.business_id, auth.connection_id, auth.external_campaign_id, auth.currency,
                 auth.hard_cap_minor, auth.daily_cap_minor, ts(auth.expires_at).isoformat()])


def consent_status(payloads: Iterable[dict[str, Any]], auth: Authorization) -> str:
    status = auth.status
    for p in payloads:
        if p.get("authorization_id") == auth.authorization_id and p.get("step") in _CONSENT_STEPS:
            status = _CONSENT_STEPS[p["step"]]
    return status


def request_consent(payloads: list[dict[str, Any]], auth: Authorization, now: datetime | str | None = None) -> dict[str, Any]:
    if consent_status(payloads, auth) != "prepared":
        raise SpendInvariantViolation("consent can only be requested for a prepared authorization")
    return {"step": "ad_spend_consent_requested", "authorization_id": auth.authorization_id,
            "terms_hash": terms_hash(auth), "snapshot_hash": snapshot_hash(auth.consent), "at": ts(now).isoformat()}


def grant_consent(payloads: list[dict[str, Any]], auth: Authorization, *, expected_terms_hash: str,
                  expected_snapshot_hash: str, receipt_id: str, now: datetime | str | None = None) -> dict[str, Any]:
    """Consent binds to the exact terms + provider snapshot that were shown to the owner."""
    t = ts(now)
    if consent_status(payloads, auth) != "pending_consent":
        raise SpendInvariantViolation("consent was not requested")
    if terms_hash(auth) != str(expected_terms_hash or "").strip():
        raise SpendInvariantViolation("consent terms changed before confirmation")
    if snapshot_hash(auth.consent) != str(expected_snapshot_hash or "").strip():
        raise SpendInvariantViolation("provider snapshot changed before confirmation")
    if t >= ts(auth.expires_at):
        raise SpendInvariantViolation("authorization expired")
    if not str(receipt_id or "").strip():
        raise ValueError("receipt_id is required")
    return {"step": "ad_spend_consent_granted", "authorization_id": auth.authorization_id,
            "receipt_id": receipt_id, "terms_hash": expected_terms_hash, "at": t.isoformat()}


def revoke_consent(payloads: list[dict[str, Any]], auth: Authorization, *, actor_member_id: str,
                   now: datetime | str | None = None) -> list[dict[str, Any]]:
    t = ts(now).isoformat()
    status = consent_status(payloads, auth)
    if status == "revoked":
        return []
    facts = [{"step": "ad_spend_consent_revoked", "authorization_id": auth.authorization_id, "at": t}]
    if status in {"launching", "active", "stopping"}:
        facts.append({"step": "ad_spend_stop_queued", "authorization_id": auth.authorization_id,
                      "business_id": auth.business_id, "reason": "revoked", "actor_member_id": actor_member_id,
                      "dry_run": True, "at": t})
    return facts


def consent_view(payloads: list[dict[str, Any]], auths: Iterable[Authorization], *, limit: int = 50) -> list[dict[str, Any]]:
    rows = [{"authorization_id": a.authorization_id, "status": consent_status(payloads, a),
             "hard_cap_minor": a.hard_cap_minor, "daily_cap_minor": a.daily_cap_minor, "currency": a.currency,
             "terms_hash": terms_hash(a), "snapshot_hash": snapshot_hash(a.consent)} for a in auths]
    return rows[: max(1, min(int(limit), 500))]


def mutations_enabled(env: dict[str, str] | None = None) -> bool:
    return str((env if env is not None else os.environ).get(MUTATIONS_ENV) or "").strip().lower() in {"1", "true", "yes", "on"}


def queue_operation(payloads: list[dict[str, Any]], auth: Authorization, kind: str, *,
                    env: dict[str, str] | None = None, now: datetime | str | None = None) -> dict[str, Any]:
    """Durable intent only; the executor processes it (dry-run). Launch needs consent AND the env gate."""
    if kind not in {"launch", "stop"}:
        raise ValueError("kind must be launch or stop")
    if kind == "launch":
        if not mutations_enabled(env):
            raise SpendInvariantViolation("advertising spend mutations are disabled")
        if consent_status(payloads, auth) != "authorized":
            raise SpendInvariantViolation("launch requires granted consent")
    return {"step": f"ad_spend_{kind}_queued", "authorization_id": auth.authorization_id,
            "business_id": auth.business_id, "dry_run": True, "at": ts(now).isoformat()}


def superseded_evidence(evidence: dict[str, Any] | None, error: BaseException) -> dict[str, Any]:
    if evidence is not None:
        return evidence
    code = error.code if isinstance(error, ProviderReadError) else type(error).__name__.lower()
    return {"operation": "launch", "provider_error_code": code,
            "provider_outcome_unknown": isinstance(error, ProviderReadError)}
