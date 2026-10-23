"""Creative trial outcomes per variant (port of donor ``creative_growth_analytics``).

Pure: the caller passes the trial dict (``creative_trials.replay``) and the ``bookings@v1`` payloads
that carry promotion attribution (``promotion_opened`` = lead, ``booked`` with ``promotion_id`` =
booking, ``promotion_won`` = won). Shared campaigns without a per-arm source token stay
unallocated and are never duplicated per arm (donor invariant). Reads only; no ad spend.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VARIANT, SHARED, UNAVAILABLE = "variant", "shared_campaign", "unavailable"
_KIND = {"promotion_opened": "leads", "booked": "bookings", "promotion_won": "won"}


def analytics_zone(env: Mapping[str, str] | None = None) -> ZoneInfo:
    e = os.environ if env is None else env
    name = (e.get("BAI_ANALYTICS_TIMEZONE") or e.get("BAI_YANDEX_DIRECT_REPORT_TIMEZONE") or "Europe/Moscow").strip()
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise RuntimeError("analytics timezone is invalid") from exc


def period(days: int, now: datetime | date | None = None, *, zone: ZoneInfo | None = None) -> tuple[str, str]:
    span = int(days)
    if span < 1 or span > 90:
        raise ValueError("creative growth analytics period must be between 1 and 90 days")
    z = zone or analytics_zone()
    if isinstance(now, datetime):
        end = now.astimezone(z).date() if now.tzinfo else now.date()
    elif isinstance(now, date):
        end = now
    else:
        end = datetime.now(z).date()
    return (end - timedelta(days=span - 1)).isoformat(), end.isoformat()


def attribution(payloads: Iterable[Mapping[str, Any]], *, date_from: str, date_to: str, zone: ZoneInfo) -> dict:
    """{kind: {campaign_id: set(customer)}} and {"source_"+kind: {token: set}} within the local window."""
    lo = datetime.fromisoformat(date_from).replace(tzinfo=zone).timestamp() * 1000
    hi = (datetime.fromisoformat(date_to).replace(tzinfo=zone) + timedelta(days=1)).timestamp() * 1000
    out: dict[str, dict[str, set[str]]] = {k: {} for k in ("leads", "bookings", "won")}
    out.update({"source_" + k: {} for k in ("leads", "bookings", "won")})
    for p in payloads:
        kind, cid = _KIND.get(str(p.get("step"))), str(p.get("promotion_id") or "")
        at = p.get("at_ms")
        if not kind or not cid or (at is not None and not lo <= int(at) < hi):
            continue
        who = str(p.get("customer_id") or "")
        out[kind].setdefault(cid, set()).add(who)
        if p.get("source_token"):
            out["source_" + kind].setdefault(str(p["source_token"]), set()).add(who)
    return out


def _n(att: Mapping[str, Mapping[str, set]], key: str, ident: str) -> int:
    return len(att.get(key, {}).get(ident, ()))


def outcomes(trial: Mapping[str, Any], att: Mapping[str, Any], *, date_from: str, date_to: str) -> dict[str, Any]:
    arms = list(trial.get("arms") or ())
    freq = Counter(a.get("promotion_campaign_id") for a in arms if a.get("promotion_campaign_id"))
    variants, shared_ids = [], set()
    for arm in arms:
        cid, tok = arm.get("promotion_campaign_id"), arm.get("promotion_source_token")
        if not cid:
            scope, nums = UNAVAILABLE, (0, 0, 0)
        elif tok:
            scope = VARIANT
            nums = tuple(_n(att, "source_" + k, tok) for k in ("leads", "bookings", "won"))
        elif freq[cid] > 1:
            scope, nums = SHARED, (0, 0, 0)
            shared_ids.add(cid)
        else:
            scope, nums = VARIANT, tuple(_n(att, k, cid) for k in ("leads", "bookings", "won"))
        variants.append({"variant_id": arm.get("variant_id"), "publication_job_id": arm.get("publication_job_id"),
                         "promotion_campaign_id": cid, "attribution_scope": scope,
                         "leads": nums[0], "bookings": nums[1], "won": nums[2]})
    shared = [{"promotion_campaign_id": c,
               "variant_ids": tuple(a.get("variant_id") for a in arms if a.get("promotion_campaign_id") == c),
               **{k: _n(att, k, c) for k in ("leads", "bookings", "won")}} for c in sorted(shared_ids)]
    return {"trial_id": trial.get("trial_id"), "date_from": date_from, "date_to": date_to,
            "variants": tuple(variants), "shared_campaigns": tuple(shared),
            "variant_level_ready": variant_level_ready(variants)}


def variant_level_ready(variants: Iterable[Mapping[str, Any]]) -> bool:
    v = list(variants)
    return bool(v) and all(x.get("attribution_scope") == VARIANT for x in v)


def get_creative_growth_outcomes(trial: Mapping[str, Any], payloads: Iterable[Mapping[str, Any]], *, days: int = 30,
                                 now: datetime | date | None = None, env: Mapping[str, str] | None = None) -> dict:
    z = analytics_zone(env)
    f, t = period(days, now, zone=z)
    return outcomes(trial, attribution(payloads, date_from=f, date_to=t, zone=z), date_from=f, date_to=t)


def _winner_trial(trial: Mapping[str, Any], snap: Mapping[str, Any]) -> dict[str, Any]:
    bps = {a.get("variant_id"): int(a.get("allocation_bps") or 0) for a in trial.get("arms") or ()}
    arms = [{"variant_id": v["variant_id"], "publication_job_id": v["publication_job_id"],
             "allocation_bps": bps.get(v["variant_id"], 0), "leads": v["leads"], "bookings": v["bookings"],
             "won": v["won"], "scope": v["attribution_scope"]} for v in snap["variants"]]
    return {"trial_id": snap["trial_id"], "revision": int(trial.get("revision") or 0),
            "running": trial.get("status", "running") == "running", "date_from": snap["date_from"],
            "date_to": snap["date_to"], "arms": arms}


def get_creative_growth_recommendation(trial: Mapping[str, Any], payloads: Iterable[Mapping[str, Any]], *,
                                       days: int = 30, now: datetime | date | None = None,
                                       env: Mapping[str, str] | None = None, **policy: Any) -> dict[str, Any]:
    """Outcomes snapshot -> reviewed allocation preview (donor creative_growth_optimization)."""
    from application.business_flows import creative_winner as cw

    snap = get_creative_growth_outcomes(trial, payloads, days=days, now=now, env=env)
    return cw.preview(_winner_trial(trial, snap), **policy)


def apply_creative_growth_recommendation(trial: Mapping[str, Any], payloads: Iterable[Mapping[str, Any]],
                                         reviewed: Mapping[str, Any], *, confirmed: bool, days: int = 30,
                                         now: datetime | date | None = None, env: Mapping[str, str] | None = None,
                                         **policy: Any) -> dict[str, Any]:
    """Explicit confirmation + CAS on revision and evidence fingerprint; returns the plan fact (no spend)."""
    from application.business_flows import creative_winner as cw

    snap = get_creative_growth_outcomes(trial, payloads, days=days, now=now, env=env)
    return cw.apply(_winner_trial(trial, snap), expected_revision=int(reviewed["revision"]),
                    expected_fingerprint=str(reviewed["fingerprint"]), confirmed=confirmed, **policy)
