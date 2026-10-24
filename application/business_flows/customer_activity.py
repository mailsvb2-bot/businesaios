"""Customer activity projection (port of donor application/customer_activity).

Pure: callers pass customer and identity records (already scoped to the tenant that the
TenantContext resolved) plus the staff and platform-admin Telegram subjects. Staff and
admins are excluded so they never count as customers. ``record_customer_contact`` touches an
already linked identity only. It never creates a shadow identity, and it returns a fact or None.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class ActivityRow:
    customer_id: str
    business_id: str
    business_name: str | None
    display_name: str | None
    username: str | None
    platforms: tuple[str, ...]
    first_contact_at: str
    last_contact_at: str


@dataclass(frozen=True)
class ActivitySummary:
    total: int
    new_today: int
    new_7d: int
    active_today: int
    by_platform: dict[str, int]
    recent: tuple[ActivityRow, ...]


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _s(value: Any) -> str:
    return str(value or "").strip()


def parse_dt(value: Any) -> datetime | None:
    raw = _s(value)
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC)


def after(value: str, boundary: datetime) -> bool:
    parsed = parse_dt(value)
    return parsed is not None and parsed >= boundary


def summarize(
    customers: list[dict[str, Any]],
    identities: list[dict[str, Any]],
    *,
    staff: dict[str, set[str]],
    admin_subjects: set[str] = frozenset(),
    exclude_platform_admins: bool = True,
    now: datetime | None = None,
    limit: int = 25,
) -> ActivitySummary:
    now = (now or utc_now()).astimezone(UTC)
    by_customer: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for ident in identities:
        if _s(ident.get("status") or "active") == "active":
            by_customer.setdefault((str(ident["business_id"]), str(ident["customer_id"])), []).append(ident)
    rows: list[ActivityRow] = []
    platform_customers: dict[str, set[tuple[str, str]]] = {}
    for c in customers:
        if _s(c.get("status") or "active") != "active":
            continue
        bid, cid = str(c["business_id"]), str(c["id"])
        idents = by_customer.get((bid, cid), [])
        tg = {_s(i.get("external_subject")) for i in idents if _s(i.get("platform")).lower() == "telegram"}
        if tg & staff.get(bid, set()) or (exclude_platform_admins and tg & set(admin_subjects)):
            continue
        first_raw, last_raw = _s(c.get("first_contact_at")), _s(c.get("last_contact_at"))
        firsts, lasts, platforms = [first_raw], [last_raw], set()
        username = name = None
        for i in idents:
            plat = _s(i.get("platform")).lower()
            if plat:
                platforms.add(plat)
                platform_customers.setdefault(plat, set()).add((bid, cid))
            username = username or _s(i.get("username")) or None
            name = name or _s(i.get("display_name")) or None
            firsts.append(_s(i.get("first_contact_at")))
            lasts.append(_s(i.get("last_contact_at")))
        fv = [(p, r) for r in firsts if (p := parse_dt(r)) is not None]
        lv = [(p, r) for r in lasts if (p := parse_dt(r)) is not None]
        rows.append(
            ActivityRow(
                cid,
                bid,
                _s(c.get("business_name")) or None,
                _s(c.get("display_name")) or name,
                username,
                tuple(sorted(platforms)),
                min(fv, key=lambda x: x[0])[1] if fv else first_raw,
                max(lv, key=lambda x: x[0])[1] if lv else last_raw,
            )
        )
    floor = datetime.min.replace(tzinfo=UTC)
    rows.sort(key=lambda r: parse_dt(r.last_contact_at) or floor, reverse=True)
    today, week = datetime(now.year, now.month, now.day, tzinfo=UTC), now - timedelta(days=7)
    return ActivitySummary(
        total=len(rows),
        new_today=sum(after(r.first_contact_at, today) for r in rows),
        new_7d=sum(after(r.first_contact_at, week) for r in rows),
        active_today=sum(after(r.last_contact_at, today) for r in rows),
        by_platform={p: len(k) for p, k in sorted(platform_customers.items())},
        recent=tuple(rows[: max(1, min(int(limit), 100))]),
    )


def tenant_activity(actor_business_id: str, customers, identities, **kw: Any) -> ActivitySummary:
    """Scope is forced to the actor's business; the caller cannot widen it."""
    bid = str(actor_business_id)
    return summarize(
        [c for c in customers if str(c.get("business_id")) == bid],
        [i for i in identities if str(i.get("business_id")) == bid],
        **kw,
    )


def platform_activity(*, is_platform_admin: bool, customers, identities, **kw: Any) -> ActivitySummary:
    if not is_platform_admin:
        raise PermissionError("platform customer activity requires platform admin")
    return summarize(customers, identities, **kw)


def record_customer_contact(
    identities: list[dict[str, Any]],
    *,
    business_id: str,
    platform: str,
    external_subject: str,
    username: str | None = None,
    display_name: str | None = None,
    at: datetime | None = None,
) -> dict[str, Any] | None:
    plat, subj = _s(platform).lower(), _s(external_subject)
    if not plat or not subj:
        raise ValueError("platform and external_subject are required")
    for i in identities:
        if (
            str(i.get("business_id")) == str(business_id)
            and _s(i.get("platform")).lower() == plat
            and _s(i.get("external_subject")) == subj
            and _s(i.get("status") or "active") == "active"
        ):
            ts = (at or utc_now()).astimezone(UTC).replace(microsecond=0).isoformat()
            return {
                "step": "customer_contact_touched",
                "business_id": str(business_id),
                "customer_id": str(i["customer_id"]),
                "platform": plat,
                "external_subject": subj,
                "username": _s(username) or None,
                "display_name": _s(display_name) or None,
                "at": ts,
            }
    return None
