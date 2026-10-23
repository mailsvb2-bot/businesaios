"""ClientPlatform DB -> BusinessAIOS flow facts (pure mapping for the migration tool).

Each donor row becomes the same fact the live command would have recorded
(``/add_slot``, ``/price``, ``/pay``, ``/lead_add``, ``/partner_add``, ``/post_add``,
``/role_add``), tagged with ``import_ref`` so re-running the import is a no-op.
Nothing here touches a database or the network; ``scripts/migration/legacy_import.py``
reads the donor SQLite read-only and appends through the Event Store.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from application.business_flows import sales as sl
from application.business_flows.projection import stable_id

SOURCE = "legacy_import"
# donor business_members.role -> core.admin.roles_read_model role ("owner" is the tenant itself)
ROLE_MAP = {"administrator": "admin", "manager": "admin", "marketer": "marketing", "content_manager": "marketing"}
LEAD_STAGE = {"new": [], "contacted": ["contact"], "qualified": ["contact", "need", "qualified"]}
LEAD_STAGE["checkout"] = [*LEAD_STAGE["qualified"], "offer", "checkout"]
LEAD_STAGE["won"] = [*LEAD_STAGE["checkout"], "paid"]
LEAD_STAGE["lost"] = ["declined"]
_BASIS = {"opted_in", "existing", "public", "unknown"}


@dataclass(frozen=True)
class Fact:
    event_type: str
    user_id: str
    timestamp_ms: int
    payload: dict[str, Any]

    @property
    def import_ref(self) -> str:
        return str(self.payload["import_ref"])

    @property
    def event_id(self) -> str:
        return stable_id("cpimp", self.event_type, self.import_ref)


def iso_ms(value: object, default: int = 0) -> int:
    if not value:
        return default
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return default
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def _tag(payload: dict[str, Any], ref: str) -> dict[str, Any]:
    return {**payload, "import_ref": ref}


Rows = Mapping[str, list[Mapping[str, Any]]]


def build_facts(rows: Rows, *, owner_user_id: str) -> tuple[list[Fact], dict[str, int]]:
    """Return facts oldest-first plus a count of skipped donor rows per table (with reason keys)."""
    out: list[Fact] = []
    skipped: dict[str, int] = {}

    def skip(key: str) -> None:
        skipped[key] = skipped.get(key, 0) + 1

    def add(event_type: str, ts: int, payload: dict[str, Any], ref: str, user: str = owner_user_id) -> None:
        out.append(Fact(event_type, str(user), ts, _tag(payload, ref)))

    offerings = {str(r["id"]): str(r["title"])[:120] for r in rows.get("business_offerings", [])}
    customers = {str(r["id"]): str(r.get("display_name") or "") for r in rows.get("customers", [])}

    for r in rows.get("business_offering_prices", []):
        title = offerings.get(str(r["offering_id"]))
        if not title or r.get("status") != "active":
            skip("business_offering_prices:archived_or_unknown_offering")
            continue
        add(
            "business_admin@v1",
            iso_ms(r.get("created_at")),
            {
                "step": "price_set",
                "offering": title,
                "amount_minor": int(r["amount_minor"]),
                "currency": str(r["currency"]).upper(),
            },
            f"price:{r['id']}",
        )

    for r in rows.get("booking_slots", []):
        start = iso_ms(r.get("starts_at"))
        title = offerings.get(str(r["offering_id"]), "Встреча")
        if not start:
            skip("booking_slots:bad_start")
            continue
        sid = stable_id("slot", start, title)
        ts = iso_ms(r.get("created_at"), start)
        add(
            "bookings@v1",
            ts,
            {
                "step": "slot_opened",
                "slot_id": sid,
                "title": title,
                "starts_at_ms": start,
                "duration_min": int(r.get("duration_minutes") or 60),
            },
            f"slot:{r['id']}",
        )
        status = str(r.get("status") or "open")
        if status == "booked" and r.get("booked_customer_id"):
            cust = f"cp:{r['booked_customer_id']}"
            add(
                "bookings@v1",
                iso_ms(r.get("booked_at"), ts),
                {"step": "booked", "slot_id": sid, "customer_id": cust},
                f"slot:{r['id']}:booked",
                cust,
            )
        elif status in ("closed", "cancelled"):
            add(
                "bookings@v1",
                iso_ms(r.get("cancelled_at") or r.get("updated_at"), ts),
                {"step": "slot_closed", "slot_id": sid},
                f"slot:{r['id']}:closed",
            )

    for r in rows.get("business_payments", []):
        title = offerings.get(str(r.get("offering_id") or ""), "") or str(r.get("note") or "Оплата")[:120]
        ref = str(r.get("external_reference") or r["id"])[:120]
        pid = stable_id("pay", ref.casefold())
        ts = iso_ms(r.get("paid_at") or r.get("created_at"))
        add(
            "business_admin@v1",
            ts,
            {
                "step": "payment_recorded",
                "payment_id": pid,
                "offering": title,
                "amount_minor": int(r["amount_minor"]),
                "currency": str(r["currency"]).upper(),
                "reference": ref,
            },
            f"pay:{r['id']}",
        )
        if str(r.get("status")) == "refunded":
            add(
                "business_admin@v1",
                iso_ms(r.get("refunded_at"), ts),
                {
                    "step": "payment_refunded",
                    "payment_id": pid,
                    "refund_id": stable_id("refund", r["id"]),
                    "amount_minor": int(r["amount_minor"]),
                },
                f"pay:{r['id']}:refund",
            )

    for r in rows.get("clientplatform_sales_leads", []):
        stage = str(r.get("stage") or "new")
        if stage not in LEAD_STAGE:
            skip("clientplatform_sales_leads:unknown_stage")
            continue
        name = (customers.get(str(r["customer_id"])) or f"Клиент {str(r['customer_id'])[:8]}")[:80]
        source = str(r.get("source_kind") or "")[:60]
        lid = stable_id("lead", f"{name.casefold()}#{r['id']}", source.casefold())
        ts = iso_ms(r.get("created_at"))
        add(
            "sales_pipeline@v1",
            ts,
            {"step": "lead_added", "lead_id": lid, "name": name, "source": source},
            f"lead:{r['id']}",
        )
        cur = "discovered"
        for i, ev in enumerate(LEAD_STAGE[stage]):
            cur = sl.reduce(sl.Stage(cur), ev).value
            add(
                "sales_pipeline@v1",
                ts + i + 1,
                {"step": "lead_event", "lead_id": lid, "event": ev, "stage": cur},
                f"lead:{r['id']}:ev{i}",
            )
        if r.get("next_action") and r.get("due_at"):
            add(
                "sales_pipeline@v1",
                ts + 50,
                {
                    "step": "lead_next",
                    "lead_id": lid,
                    "text": str(r["next_action"])[:200],
                    "due_ms": iso_ms(r["due_at"]),
                },
                f"lead:{r['id']}:next",
            )

    for r in rows.get("partner_candidates", []):
        try:
            tags = [str(t)[:40] for t in json.loads(r.get("tags_json") or "[]")][:12]
        except ValueError:
            tags = []
        basis = str(r.get("contact_basis") or "unknown")
        add(
            "partners@v1",
            iso_ms(r.get("discovered_at") or r.get("created_at")),
            {
                "step": "partner_added",
                "partner_id": stable_id("partner", str(r["name"]).casefold()),
                "name": str(r["name"])[:120],
                "tags": tags,
                "followers": int(r["follower_count"]) if r.get("follower_count") is not None else None,
                "basis": basis if basis in _BASIS else "unknown",
                "contact": str(r.get("contact_value") or "")[:200],
                "competitor": bool(r.get("competitor")),
            },
            f"partner:{r['id']}",
        )

    for r in rows.get("business_publications", []):
        pid = stable_id("pub", r["id"])
        ts = iso_ms(r.get("created_at"))
        add(
            "business_admin@v1",
            ts,
            {
                "step": "pub_draft",
                "pub_id": pid,
                "channel": str(r.get("channel") or "telegram"),
                "title": str(r["title"])[:120],
                "body": str(r["body"])[:4000],
                "at_ms": ts,
            },
            f"pub:{r['id']}",
        )
        status = str(r.get("status") or "draft")
        if status == "scheduled" and r.get("scheduled_at"):
            add(
                "business_admin@v1",
                ts + 1,
                {"step": "pub_scheduled", "pub_id": pid, "at_ms": iso_ms(r["scheduled_at"])},
                f"pub:{r['id']}:sched",
            )
        elif status == "published":
            add(
                "business_admin@v1",
                ts + 1,
                {"step": "pub_published", "pub_id": pid, "at_ms": iso_ms(r.get("published_at"), ts)},
                f"pub:{r['id']}:pub",
            )
        elif status != "draft":
            add("business_admin@v1", ts + 1, {"step": "pub_retired", "pub_id": pid, "at_ms": ts}, f"pub:{r['id']}:ret")

    for r in rows.get("business_members", []):
        role = ROLE_MAP.get(str(r["role"]), "" if r["role"] == "owner" else str(r["role"]))
        if not role:
            skip("business_members:owner_is_tenant")
            continue
        add(
            "admin_role_set",
            iso_ms(r.get("created_at")),
            {
                "admin_id": owner_user_id,
                "target_user_id": str(r["user_id"]),
                "role": role,
                "enabled": str(r.get("status")) == "active",
            },
            f"member:{r['id']}",
        )

    out.sort(key=lambda f: f.timestamp_ms)
    return out, skipped


def plan(facts: Iterable[Fact], existing_refs: set[tuple[str, str]]) -> list[Fact]:
    """Facts not yet imported (idempotency by (event_type, import_ref))."""
    return [f for f in facts if (f.event_type, f.import_ref) not in existing_refs]


def existing_refs(
    iter_events: Callable[..., Iterable[Mapping[str, Any]]], *, tenant_id: str, event_types: Iterable[str]
) -> set[tuple[str, str]]:
    refs: set[tuple[str, str]] = set()
    for et in set(event_types):
        for ev in iter_events(tenant_id=tenant_id, start_ms=0, end_ms=None, event_type=et):
            p = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
            if p.get("import_ref"):
                refs.add((et, str(p["import_ref"])))
    return refs


def to_event(fact: Fact, *, tenant_id: str) -> dict[str, Any]:
    return {
        "event_id": fact.event_id,
        "tenant_id": tenant_id,
        "user_id": fact.user_id,
        "source": SOURCE,
        "event_type": fact.event_type,
        "timestamp_ms": fact.timestamp_ms,
        "decision_id": None,
        "correlation_id": f"{SOURCE}:{fact.import_ref}",
        "payload": fact.payload,
    }
