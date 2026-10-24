"""Fail-closed ad spend guard (port of clientplatform ad_spend_runtime + ad_spend_control guard).

Pure decision logic over an owner authorization and a READ-ONLY provider budget snapshot.
Nothing here mutates a provider or spends money: a sweep only yields ``ad_spend_stop_queued``
facts (dry-run stop requests) that the executor records; live provider stop/launch stays
behind ``ad_proposals.publish_decision`` (production_ready=False -> blocked).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections.abc import Callable, Iterable, Mapping
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
                  "ad_spend_consent_revoked": "revoked", "ad_spend_launch_queued": "launching", "ad_spend_launched": "active",
                  "ad_spend_stop_queued": "stopping", "ad_spend_stopped": "stopped", "ad_spend_launch_failed": "failed"}


def _sha(obj: object) -> str:
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


# --- provider port, session, authorization preparation, goal caps, operation processing -------------------
# Everything below is pure over injected ports/fakes. Real provider access is the executor effect
# ``ad_provider_action`` (flags BAI_AD_SPEND_PROVIDER_ENABLED / BAI_AD_SPEND_MUTATIONS_ENABLED, both off by default);
# secrets are only ``env:`` / ``vault:`` references and are never stored in facts.
PROVIDER_ENV = "BAI_AD_SPEND_PROVIDER_ENABLED"
CEILING_ENV = "BAI_AD_SPEND_CEILING_MINOR"
GOAL_MAX_ENV, GOAL_DAILY_ENV = "BAI_GOAL_MAX_SPEND_MINOR", "BAI_GOAL_DAILY_SPEND_MINOR"
CONNECTIONS_ENV = "BUSINESAIOS_AD_CONNECTIONS"
DEFAULT_MAX_SPEND_MINOR, MICROS_PER_MINOR = 10_000, 10_000
MAX_ATTEMPTS, LEASE_SECONDS = 8, 60
_REF = re.compile(r"^(env|vault):[A-Za-z_][A-Za-z0-9_]{0,63}$")
_TRUE = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BudgetReadout:
    """Read-only provider evidence for one campaign (budget + today's spend + provider minimum)."""
    external_account_id: str
    external_campaign_id: str
    currency: str
    available_budget_minor: int
    spent_today_minor: int
    strategy: str
    report_date: str
    minimum_weekly_micros: int = 0
    launch_eligible: bool = True


@dataclass(frozen=True)
class GoalSpendPreview:
    connection_id: str
    external_campaign_id: str
    currency: str
    recommended_hard_cap_minor: int
    recommended_daily_cap_minor: int
    available_budget_minor: int
    spent_today_minor: int


class AdProviderPort:
    """Interface (duck-typed) of an advertising provider; tests use fakes, production uses the executor effect."""

    def read_budget(self, access_token: str, *, campaign_id: str, report_date: str, now: datetime) -> BudgetReadout:
        raise NotImplementedError

    def refresh(self, bundle: Mapping[str, str]) -> dict[str, str]:
        raise NotImplementedError

    def configure_budget(self, access_token: str, *, campaign_id: str, hard_cap_minor: int, daily_cap_minor: int,
                         idempotency_key: str) -> dict[str, Any]:
        raise NotImplementedError

    def moderate_ad(self, access_token: str, *, campaign_id: str, idempotency_key: str) -> dict[str, Any]:
        raise NotImplementedError

    def suspend_ad(self, access_token: str, *, campaign_id: str, idempotency_key: str) -> dict[str, Any]:
        raise NotImplementedError


class DryRunAdProvider(AdProviderPort):
    """Used while the flags are off: no external call; reads fail closed, mutations are recorded as dry runs."""

    def read_budget(self, access_token: str, **kw: Any) -> BudgetReadout:
        raise ProviderReadError("provider_dry_run")

    def refresh(self, bundle: Mapping[str, str]) -> dict[str, str]:
        raise ProviderReadError("provider_dry_run")

    def configure_budget(self, access_token: str, **kw: Any) -> dict[str, Any]:
        return {"dry_run": True, "action": "configure_budget"}

    def moderate_ad(self, access_token: str, **kw: Any) -> dict[str, Any]:
        return {"dry_run": True, "action": "moderate_ad"}

    def suspend_ad(self, access_token: str, **kw: Any) -> dict[str, Any]:
        return {"dry_run": True, "action": "suspend_ad"}


def _flag(name: str, env: Mapping[str, str] | None) -> bool:
    return str((env if env is not None else os.environ).get(name) or "").strip().lower() in _TRUE


def provider_enabled(env: Mapping[str, str] | None = None) -> bool:
    return _flag(PROVIDER_ENV, env)


def utc_now() -> datetime:
    """Donor ``_utc_now``."""
    return ts(None)


def authorization_expiry(value: datetime | str) -> datetime:
    """Donor ``_expiry``: an aware timestamp or ValueError."""
    try:
        return ts(value)
    except ValueError as exc:
        raise ValueError("authorization_expires_at must be timezone-aware") from exc


def check_report_date(value: object, *, now: datetime) -> str:
    """Donor ``_report_date``: YYYY-MM-DD within one day of the current account day."""
    from datetime import date
    if isinstance(value, datetime):
        raise ValueError("provider_report_date must not include time")
    try:
        parsed = value if isinstance(value, date) else date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError("provider_report_date must use YYYY-MM-DD") from exc
    if abs((parsed - now.date()).days) > 1:
        raise SpendInvariantViolation("provider report date is outside the current account-day boundary")
    return parsed.isoformat()


def authorization_ttl(expires_at: datetime, now: datetime) -> int:
    ttl = math.ceil((expires_at - now).total_seconds())
    if not 1 <= ttl <= 300:
        raise SpendInvariantViolation("authorization validity must be between 1 and 300 seconds")
    return ttl


def spend_ceiling(env: Mapping[str, str] | None = None) -> int:
    """Absolute per-authorization ceiling (minor units); 0 = not configured = spending is impossible."""
    raw = str((env if env is not None else os.environ).get(CEILING_ENV) or "").strip()
    return int(raw) if raw.isdigit() else 0


def check_ceiling(hard_cap_minor: int, daily_cap_minor: int, env: Mapping[str, str] | None = None) -> None:
    ceiling = spend_ceiling(env)
    if ceiling <= 0:
        raise SpendInvariantViolation(f"{CEILING_ENV} is not configured: advertising spend is impossible")
    if type(hard_cap_minor) is not int or type(daily_cap_minor) is not int or not 0 < daily_cap_minor <= hard_cap_minor:
        raise SpendInvariantViolation("spend caps must be positive integers with daily <= total")
    if hard_cap_minor > ceiling:
        raise SpendInvariantViolation("requested spend exceeds the configured ceiling")


def configured_minor(name: str, default: int, env: Mapping[str, str] | None = None) -> int:
    """Donor ``_configured_minor``."""
    raw = str((env if env is not None else os.environ).get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer number of minor currency units") from exc
    if value <= 0 or value > 9_000_000_000_000_000:
        raise RuntimeError(f"{name} is outside the supported range")
    return value


def minimum_weekly_minor(micros: object) -> int:
    if isinstance(micros, bool | float) or not isinstance(micros, int) or micros <= 0:
        raise SpendInvariantViolation("provider minimum weekly budget is invalid")
    minor, rest = divmod(micros, MICROS_PER_MINOR)
    if rest or minor <= 0:
        raise SpendInvariantViolation("provider minimum weekly budget cannot be represented in minor currency units")
    return minor


def goal_caps(available_budget_minor: int, *, minimum_weekly_micros: int, env: Mapping[str, str] | None = None) -> tuple[int, int]:
    """Goal-first caps (donor ``_caps``): operator maximum or default, never above the available budget."""
    e = env if env is not None else os.environ
    floor = minimum_weekly_minor(minimum_weekly_micros)
    hard_set = bool(str(e.get(GOAL_MAX_ENV) or "").strip())
    configured = configured_minor(GOAL_MAX_ENV, DEFAULT_MAX_SPEND_MINOR, e)
    if hard_set and configured < floor:
        raise SpendInvariantViolation("configured goal spend maximum is below the provider minimum weekly budget")
    hard = min(configured if hard_set else max(configured, floor), int(available_budget_minor))
    if hard < floor:
        raise SpendInvariantViolation("available provider budget is below the minimum weekly budget")
    daily_set = bool(str(e.get(GOAL_DAILY_ENV) or "").strip())
    daily = min(configured_minor(GOAL_DAILY_ENV, hard, e), hard)
    if min(hard, daily * 7) * MICROS_PER_MINOR < minimum_weekly_micros:
        raise SpendInvariantViolation("configured goal daily spend maximum is below the provider minimum weekly budget"
                                      if daily_set else "goal-first spend cap is below the provider minimum weekly budget")
    return hard, daily


# -- session: secret references only, refresh once on an auth error
def secret_ref(value: object) -> str:
    ref = str(value or "").strip()
    if not _REF.match(ref):
        raise ValueError("secret must be an env:NAME or vault:NAME reference, never a raw value")
    return ref


class AdVault:
    """Resolves token bundles by reference through an injected resolver (``ref -> str | None``)."""

    def __init__(self, resolve: Callable[[str], str | None]) -> None:
        self._resolve = resolve

    def bundle(self, ref: str) -> dict[str, str]:
        raw = self._resolve(secret_ref(ref))
        try:
            data = json.loads(raw or "")
        except (TypeError, ValueError) as exc:
            raise ProviderReadError("oauth_bundle_unavailable") from exc
        if not isinstance(data, dict) or not str(data.get("access_token") or "").strip():
            raise ProviderReadError("oauth_bundle_unavailable")
        return {str(k): str(v) for k, v in data.items()}


def ad_vault(resolve: Callable[[str], str | None] | None = None) -> AdVault:
    """Donor ``ad_vault`` / ``_vault``: secrets are resolved only on demand; no resolver = nothing resolvable."""
    return AdVault(resolve or (lambda ref: None))


def load_bundle(vault: AdVault, ref: str) -> dict[str, str]:
    return vault.bundle(ref)


def refresh_bundle(provider: AdProviderPort, bundle: Mapping[str, str], *, save: Callable[[dict[str, str]], None] | None = None) -> dict[str, str]:
    """Donor ``refresh_bundle``/``_refresh_bundle``: refresh through the provider, persist via ``save`` when given."""
    fresh = dict(provider.refresh(bundle))
    if not str(fresh.get("access_token") or "").strip():
        raise ProviderReadError("oauth_refresh_failed")
    if save is not None:
        save(fresh)
    return fresh


def with_access_token(call: Callable[[str], Any], bundle: Mapping[str, str], *, refresh: Callable[[Mapping[str, str]], dict[str, str]] | None):
    """Run ``call(access_token)``; on an auth error refresh ONCE and retry. Returns (result, bundle_used)."""
    try:
        return call(bundle["access_token"]), dict(bundle)
    except ProviderReadError as exc:
        if exc.code not in AUTH_ERRORS or not bundle.get("refresh_token") or refresh is None:
            raise
        fresh = refresh(bundle)
        return call(fresh["access_token"]), fresh


def redirect_uri(env: Mapping[str, str] | None = None) -> str:
    """Donor ``_redirect_uri``."""
    e = env if env is not None else os.environ
    explicit = str(e.get("BAI_AD_OAUTH_REDIRECT_URI") or "").strip()
    if explicit:
        return explicit
    domain = str(e.get("BAI_DOMAIN") or "").strip()
    if not domain:
        raise RuntimeError("BAI_DOMAIN is required for advertising OAuth")
    return f"https://{domain}/oauth/yandex-direct/callback"


def yandex_provider(factory: Callable[[], AdProviderPort], env: Mapping[str, str] | None = None) -> AdProviderPort:
    """Donor ``yandex_provider`` / ``_provider``: refuses unless connections are enabled and configured.

    The real provider is built by ``factory`` only when ``BAI_AD_SPEND_PROVIDER_ENABLED`` is on; otherwise a
    DryRunAdProvider (no external call) is returned.
    """
    e = env if env is not None else os.environ
    if not _flag(CONNECTIONS_ENV, e):
        raise RuntimeError("advertising account connections are disabled")
    if not str(e.get("YANDEX_DIRECT_CLIENT_ID") or "").strip():
        raise RuntimeError("Yandex Direct OAuth application is not configured")
    secret_ref(e.get("YANDEX_DIRECT_CLIENT_SECRET_REF"))
    redirect_uri(e)
    return factory() if provider_enabled(e) else DryRunAdProvider()


def read_provider_evidence(provider: AdProviderPort, bundle: Mapping[str, str], *, campaign_id: str, report_date: str,
                           now: datetime, refresh: Callable[[Mapping[str, str]], dict[str, str]] | None = None
                           ) -> tuple[BudgetReadout, dict[str, str]]:
    """Donor ``_read_provider_evidence``: one read-only readout, refresh once on an auth error."""
    return with_access_token(lambda tok: provider.read_budget(tok, campaign_id=campaign_id, report_date=report_date, now=now),
                             bundle, refresh=refresh)


def read_goal_evidence(provider: AdProviderPort, bundle: Mapping[str, str], *, campaign_id: str, now: datetime,
                       tz: ZoneInfo, refresh: Callable[[Mapping[str, str]], dict[str, str]] | None = None
                       ) -> tuple[BudgetReadout, str, dict[str, str]]:
    """Donor ``_read_goal_evidence``: readout + report date + provider minimum, before any draft exists."""
    day = provider_report_date(now, tz)

    def read(token: str) -> BudgetReadout:
        out = provider.read_budget(token, campaign_id=campaign_id, report_date=day, now=now)
        if out.minimum_weekly_micros <= 0:
            raise ProviderReadError("provider_minimum_unavailable")
        return out

    out, used = with_access_token(read, bundle, refresh=refresh)
    if out.report_date and out.report_date != day:
        raise SpendInvariantViolation("provider report date mismatch")
    return out, day, used


def preview_goal_spend(provider: AdProviderPort, bundle: Mapping[str, str], *, connection_id: str, campaign_id: str,
                       now: datetime | str | None = None, tz: ZoneInfo, env: Mapping[str, str] | None = None,
                       refresh: Callable[[Mapping[str, str]], dict[str, str]] | None = None) -> GoalSpendPreview:
    """Exact bounded caps for the owner before the explicit launch button; performs no mutation."""
    t = ts(now).replace(microsecond=0)
    out, _, _ = read_goal_evidence(provider, bundle, campaign_id=campaign_id, now=t, tz=tz, refresh=refresh)
    hard, daily = goal_caps(out.available_budget_minor, minimum_weekly_micros=out.minimum_weekly_micros, env=env)
    check_ceiling(hard, daily, env)
    return GoalSpendPreview(connection_id, out.external_campaign_id, out.currency, hard, daily,
                            out.available_budget_minor, out.spent_today_minor)


def snapshot_of(out: BudgetReadout, *, connection_id: str, captured_at: datetime) -> Snapshot:
    return Snapshot(connection_id, out.external_account_id, out.external_campaign_id, out.currency, out.spent_today_minor,
                    out.strategy, ts(captured_at), out.launch_eligible, out.report_date)


def _snap_dict(s: Snapshot) -> dict[str, Any]:
    return {"connection_id": s.connection_id, "external_account_id": s.external_account_id,
            "external_campaign_id": s.external_campaign_id, "currency": s.currency,
            "spent_today_minor": s.spent_today_minor, "strategy": s.strategy,
            "captured_at": ts(s.captured_at).isoformat(), "launch_eligible": s.launch_eligible, "report_date": s.report_date}


def prepare_authorization(provider: AdProviderPort, bundle: Mapping[str, str], *, business_id: str, connection_id: str,
                          external_account_id: str, external_campaign_id: str, hard_cap_minor: int, daily_cap_minor: int,
                          expires_at: datetime | str, report_date: object, tz: ZoneInfo, now: datetime | str | None = None,
                          env: Mapping[str, str] | None = None,
                          refresh: Callable[[Mapping[str, str]], dict[str, str]] | None = None) -> tuple[Authorization, dict[str, Any]]:
    """Donor ``prepare_ad_spend_authorization``: fresh read-only evidence -> a prepared authorization fact.

    Spends nothing and mutates nothing; consent and launch are separate, explicit owner steps.
    """
    t = ts(now)
    exp = authorization_expiry(expires_at)
    ttl = authorization_ttl(exp, t)
    day = check_report_date(report_date, now=t)
    check_ceiling(hard_cap_minor, daily_cap_minor, env)
    out, _ = read_provider_evidence(provider, bundle, campaign_id=external_campaign_id, report_date=day, now=t, refresh=refresh)
    if out.external_account_id != external_account_id or out.external_campaign_id != external_campaign_id:
        raise SpendInvariantViolation("advertising account changed during authorization preparation")
    if out.report_date and out.report_date != day:
        raise SpendInvariantViolation("provider report date mismatch")
    if not out.launch_eligible:
        raise SpendInvariantViolation("provider evidence is not eligible for advertising spend")
    if int(hard_cap_minor) > int(out.available_budget_minor):
        raise SpendInvariantViolation("requested spend exceeds the available provider budget")
    weekly = min(int(hard_cap_minor), int(daily_cap_minor) * 7) * MICROS_PER_MINOR
    if weekly < int(out.minimum_weekly_micros):
        raise SpendInvariantViolation("spend caps are below the provider minimum weekly budget")
    snap = snapshot_of(out, connection_id=connection_id, captured_at=t)
    aid = "adsp_" + _sha([business_id, connection_id, external_campaign_id, hard_cap_minor, daily_cap_minor, exp.isoformat()])[:24]
    auth = Authorization(aid, business_id, connection_id, external_campaign_id, out.currency, int(hard_cap_minor),
                         int(daily_cap_minor), exp, "prepared", snap)
    return auth, {"step": "ad_spend_prepared", "authorization_id": aid, "business_id": business_id, "ttl_seconds": ttl,
                  "hard_cap_minor": int(hard_cap_minor), "daily_cap_minor": int(daily_cap_minor), "currency": out.currency,
                  "expires_at": exp.isoformat(), "snapshot": _snap_dict(snap), "at": t.isoformat()}


def authorizations_replay(payloads: Iterable[dict[str, Any]]) -> dict[str, Authorization]:
    out: dict[str, Authorization] = {}
    for p in payloads:
        if p.get("step") != "ad_spend_prepared" or p.get("authorization_id") in out:
            continue
        sn = dict(p["snapshot"])
        snap = Snapshot(sn["connection_id"], sn["external_account_id"], sn["external_campaign_id"], sn["currency"],
                        int(sn["spent_today_minor"]), sn["strategy"], ts(sn["captured_at"]), bool(sn["launch_eligible"]),
                        sn.get("report_date", ""))
        out[p["authorization_id"]] = Authorization(p["authorization_id"], p["business_id"], snap.connection_id,
                                                   snap.external_campaign_id, p["currency"], int(p["hard_cap_minor"]),
                                                   int(p["daily_cap_minor"]), ts(p["expires_at"]), "prepared", snap)
    return out


def with_status(payloads: list[dict[str, Any]], auth: Authorization) -> Authorization:
    from dataclasses import replace
    return replace(auth, status=consent_status(payloads, auth))


def launch_or_dry_run(payloads: list[dict[str, Any]], auth: Authorization, *, env: Mapping[str, str] | None = None,
                      now: datetime | str | None = None) -> dict[str, Any]:
    """Explicit owner launch. Consent + ceiling are mandatory; with the mutations flag off it is a dry-run fact only."""
    if consent_status(payloads, auth) != "authorized":
        raise SpendInvariantViolation("launch requires granted consent")
    check_ceiling(auth.hard_cap_minor, auth.daily_cap_minor, env)
    if ts(now) >= ts(auth.expires_at):
        raise SpendInvariantViolation("authorization expired")
    if not mutations_enabled(dict(env) if env is not None else None):
        return {"step": "ad_spend_launch_dry_run", "authorization_id": auth.authorization_id,
                "business_id": auth.business_id, "flag": MUTATIONS_ENV, "at": ts(now).isoformat()}
    return queue_operation(payloads, auth, "launch", env=dict(env) if env is not None else None, now=now)


def current_launch_authorization(auths: Mapping[str, Authorization], payloads: list[dict[str, Any]], authorization_id: str,
                                 *, now: datetime | str | None = None, env: Mapping[str, str] | None = None) -> Authorization:
    """Donor ``_current_launch_authorization``: re-checked right before the provider is touched."""
    base = auths.get(authorization_id)
    if base is None:
        raise SpendInvariantViolation("authorization not found")
    auth = with_status(payloads, base)
    if auth.status != "launching":
        raise SpendInvariantViolation("authorization is not in the launching state")
    if ts(now) >= ts(auth.expires_at):
        raise SpendInvariantViolation("authorization expired")
    check_ceiling(auth.hard_cap_minor, auth.daily_cap_minor, env)
    return auth


# -- durable operation queue: lease, retry, supersession, idempotency
def op_id(authorization_id: str, kind: str) -> str:
    return "adop_" + _sha([authorization_id, kind])[:24]


@dataclass
class Op:
    op_id: str
    authorization_id: str
    kind: str
    state: str = "queued"  # queued | leased | done | failed | dead
    attempts: int = 0
    lease_until: datetime | None = None
    available_at: datetime | None = None
    evidence: dict[str, Any] | None = None


def ops_replay(payloads: Iterable[dict[str, Any]]) -> dict[str, Op]:
    ops: dict[str, Op] = {}
    for p in payloads:
        step = str(p.get("step") or "")
        if step in {"ad_spend_launch_queued", "ad_spend_stop_queued"}:
            kind = "launch" if "launch" in step else "stop"
            oid = op_id(str(p["authorization_id"]), kind)
            ops.setdefault(oid, Op(oid, str(p["authorization_id"]), kind))
            continue
        op = ops.get(str(p.get("op_id") or ""))
        if op is None or op.state == "done":
            continue
        if step == "ad_spend_op_claimed":
            op.state, op.attempts, op.lease_until = "leased", int(p["attempt"]), ts(p["lease_until"])
        elif step == "ad_spend_op_completed":
            op.state, op.evidence = "done", dict(p.get("evidence") or {})
        elif step == "ad_spend_op_failed":
            retry = bool(p.get("retryable")) and op.attempts < int(p.get("max_attempts") or MAX_ATTEMPTS)
            op.state, op.evidence = ("failed" if retry else "dead"), {"code": p.get("code")}
            op.available_at = ts(p["available_at"]) if retry else None
    return ops


def due_operation(ops: Mapping[str, Op], now: datetime) -> Op | None:
    """First claimable op: queued, retry-ready, or a lease that went stale (crash recovery)."""
    for op in ops.values():
        if op.attempts >= MAX_ATTEMPTS and op.state != "queued":
            continue
        if op.state == "queued" or (op.state == "failed" and op.available_at and op.available_at <= now) \
                or (op.state == "leased" and op.lease_until and op.lease_until <= now):
            return op
    return None


def _fail(op: Op, code: str, *, retryable: bool, now: datetime, extra: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    delay = min(30 * 2 ** max(op.attempts, 1), 3600)
    out = [{"step": "ad_spend_op_failed", "op_id": op.op_id, "authorization_id": op.authorization_id, "code": code,
            "retryable": retryable, "max_attempts": MAX_ATTEMPTS, "available_at": (now + timedelta(seconds=delay)).isoformat(),
            "at": now.isoformat(), **(extra or {})}]
    if op.kind == "launch" and (not retryable or op.attempts >= MAX_ATTEMPTS):  # terminal: nothing was launched
        out.append({"step": "ad_spend_launch_failed", "authorization_id": op.authorization_id, "code": code, "at": now.isoformat()})
    return out


def process_one_operation(payloads: list[dict[str, Any]], provider: AdProviderPort, bundle: Mapping[str, str], *,
                          tz: ZoneInfo, env: Mapping[str, str] | None = None, now: datetime | str | None = None,
                          refresh: Callable[[Mapping[str, str]], dict[str, str]] | None = None) -> list[dict[str, Any]]:
    """Donor ``process_one_ad_spend_operation`` over facts. Returns the facts to record (empty = nothing due).

    claim(lease) -> re-check authorization -> fresh read-only guard -> configure_budget -> moderate_ad (launch) or
    suspend_ad (stop). Every provider mutation carries a deterministic idempotency key. A launch that was
    superseded by a stop completes with evidence and never touches the provider.
    """
    t = ts(now)
    ops = ops_replay(payloads)
    op = due_operation(ops, t)
    if op is None:
        return []
    recovered = op.state == "leased"
    op.attempts += 1
    facts: list[dict[str, Any]] = [{"step": "ad_spend_op_claimed", "op_id": op.op_id, "authorization_id": op.authorization_id,
                                    "attempt": op.attempts, "lease_until": (t + timedelta(seconds=LEASE_SECONDS)).isoformat(),
                                    "recovered_stale_lease": recovered, "at": t.isoformat()}]
    auths = authorizations_replay(payloads)
    try:
        if op.kind == "launch" and op_id(op.authorization_id, "stop") in ops:
            return facts + [{"step": "ad_spend_op_completed", "op_id": op.op_id, "authorization_id": op.authorization_id,
                             "evidence": {"operation": "launch", "superseded": True, "reason": "superseded_by_stop"},
                             "at": t.isoformat()}]
        base = auths.get(op.authorization_id)
        if base is None:
            return facts + _fail(op, "authorization_missing", retryable=False, now=t)
        if op.kind == "launch":
            auth = current_launch_authorization(auths, payloads, op.authorization_id, now=t, env=env)
            snap, newtok = fresh_snapshot(auth, account_id=auth.consent.external_account_id, token=dict(bundle),
                                     read=lambda tok, a, day, when: snapshot_of(
                                         provider.read_budget(tok, campaign_id=a.external_campaign_id, report_date=day, now=when),
                                         connection_id=a.connection_id, captured_at=when),
                                     refresh=refresh, tz=tz, now=t)
            bundle = newtok or bundle
            verdict = runtime_guard(auth, snap, tz, t)
            if not verdict.allowed:
                return facts + _fail(op, f"guard_{verdict.reason}", retryable=False, now=t)
            budget = provider.configure_budget(bundle["access_token"], campaign_id=auth.external_campaign_id,
                                               hard_cap_minor=auth.hard_cap_minor, daily_cap_minor=auth.daily_cap_minor,
                                               idempotency_key=f"{op.op_id}:budget")
            moderated = provider.moderate_ad(bundle["access_token"], campaign_id=auth.external_campaign_id,
                                             idempotency_key=f"{op.op_id}:moderate")
            dry = bool(budget.get("dry_run") or moderated.get("dry_run"))
            done = {"step": "ad_spend_op_completed", "op_id": op.op_id, "authorization_id": op.authorization_id,
                    "evidence": {"operation": "launch", "budget": budget, "moderation": moderated, "dry_run": dry}, "at": t.isoformat()}
            return facts + [done] + ([] if dry else [{"step": "ad_spend_launched", "authorization_id": op.authorization_id, "at": t.isoformat()}])
        stopped = provider.suspend_ad(bundle["access_token"], campaign_id=base.external_campaign_id, idempotency_key=f"{op.op_id}:suspend")
        dry = bool(stopped.get("dry_run"))
        done = {"step": "ad_spend_op_completed", "op_id": op.op_id, "authorization_id": op.authorization_id,
                "evidence": {"operation": "stop", "suspend": stopped, "dry_run": dry}, "at": t.isoformat()}
        return facts + [done] + ([] if dry else [{"step": "ad_spend_stopped", "authorization_id": op.authorization_id, "at": t.isoformat()}])
    except ProviderReadError as exc:
        return facts + _fail(op, exc.code, retryable=exc.code != "provider_dry_run", now=t,
                              extra={"outcome_unknown": op.kind == "launch"})
    except (SpendInvariantViolation, ValueError, KeyError) as exc:
        return facts + _fail(op, type(exc).__name__.lower() + ":" + str(exc)[:120], retryable=False, now=t)


# -- owner messages (donor _ad_spend_launch_message / _event_promotion_yandex_message)
def launch_message(outcome: str, operation_id: str = "") -> str:
    """outcome: queued | dry_run | denied | unavailable. Never claims money was spent unless the provider confirmed it."""
    if outcome == "queued":
        return ("🚀 Запуск поставлен в защищённую идемпотентную очередь.\n\nПеред обращением к рекламному провайдеру "
                "сервер ещё раз проверит кабинет, срок, расход и точные подтверждённые лимиты. При расхождении запуск "
                f"будет заблокирован.\n\nОперация: …{operation_id[-12:]}")
    if outcome == "dry_run":
        return f"🔒 Запуск рекламы выключен ({MUTATIONS_ENV}): записано как пробный запуск, ничего не потрачено."
    if outcome == "unavailable":
        return "Безопасный запуск сейчас недоступен. Ничего не потрачено."
    return "Запуск запрещён, устарел или состояние разрешения изменилось. Ничего не потрачено."


def event_promotion_message(title: str, url: str, *, env: Mapping[str, str] | None = None) -> str:
    cabinet = ("✅ чтение рекламного кабинета включено" if provider_enabled(env)
               else f"⚪ кабинет не подключён ({PROVIDER_ENV} выключен)")
    return (f"📡 Яндекс Директ · вебинар\n\n{title}\n\nКабинет: {cabinet}\n\nПосадочная страница объявления:\n{url}\n\n"
            "Для вебинара используйте именно эту event-ссылку. Она сохраняет source=ads и campaign_ref конкретного "
            "мероприятия; регистрация остаётся в event CRM и не смешивается с записью на услуги.")
