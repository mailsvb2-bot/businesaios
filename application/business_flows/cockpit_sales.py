"""Owner cockpit sales screens (donor native_member_interactions sales workspace).

Pure: renders ``(text, rows)`` from the sales_pipeline projection and turns a stage
button into the same ``lead_event`` fact ``/lead`` produces (one reducer: sales.reduce).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from application.business_flows import sales as sl

CANON_COCKPIT_SALES = True
S = sl.Stage
CLOSED = (S.WON, S.LOST)
# donor stage buttons: contacted / qualified / checkout, then "paid" / "lost"
NEXT_EVENT = {
    S.DISCOVERED: "contact",
    S.ENGAGED: "need",
    S.NEED_KNOWN: "qualified",
    S.QUALIFIED: "offer",
    S.OFFER_PRESENTED: "checkout",
}
EVENT_LABELS = {
    "contact": "Связались",
    "need": "Потребность ясна",
    "qualified": "Интерес",
    "offer": "Предложение",
    "checkout": "Оформление",
    "paid": "✅ Оплатил",
    "declined": "❌ Не состоялось",
    "handoff": "🙋 Нужен человек",
    "resume": "▶️ Вернуть в работу",
}
PARENTS = {
    "sales": "cpm:work",
    "sales-lead": "cpm:sales",
    "sales-actions": "cpm:sales",
    "sales-recent": "cpm:sales",
    "sales-handoffs": "cpm:sales",
}
SCREENS = frozenset(PARENTS) | {"sales-ev"}


def _lead(st: Any, lead_id: str) -> sl.Lead:
    lead = (getattr(st, "leads", None) or {}).get(lead_id)
    if lead is None:
        raise ValueError("unknown lead")
    return lead


def _primary(lead: sl.Lead) -> tuple[str, str] | None:
    """Donor _sales_primary_button: one main next step for an open lead."""
    if lead.stage in CLOSED:
        return None
    if lead.handoff_open:
        return EVENT_LABELS["resume"], f"cpm:sales-ev:{lead.lead_id}:resume"
    ev = NEXT_EVENT.get(lead.stage, "paid")
    return EVENT_LABELS[ev], f"cpm:sales-ev:{lead.lead_id}:{ev}"


def screen(action: str, args: tuple[str, ...], st: Any, *, now_ms: int) -> tuple[str, list[list[tuple[str, str]]]]:
    leads = sl.ordered(st) if st is not None else []
    if action == "sales":
        open_leads = [x for x in leads if x.stage not in CLOSED][:6]
        rows: list[list[tuple[str, str]]] = []
        if any(x.handoff_open for x in leads):
            rows.append([("🙋 Нужно подключиться", "cpm:sales-handoffs")])
        lines = [f"• {x.name} · {sl.LABELS[x.stage]}" for x in open_leads] or ["Открытых обращений сейчас нет."]
        rows += [[(x.name[:32], f"cpm:sales-lead:{x.lead_id}")] for x in open_leads]
        due = len(sl.due_actions(st, now_ms=now_ms)) if st is not None else 0
        rows.append([("🗂 Недавно закрытые", "cpm:sales-recent")])
        tail = f"\n\nПросрочено шагов: {due} (/leads_due)" if due else ""
        return "💬 Обращения и продажи\n\n" + "\n".join(lines) + tail + "\n\nНовый лид: /lead_add Имя | источник", rows
    if action == "sales-lead":
        lead = _lead(st, args[0] if args else "")
        nxt = lead.next_action or "не задан (/lead_next)"
        text = (
            f"💬 {lead.name}\n\nСтадия: {sl.LABELS[lead.stage]}\nИсточник: {lead.source or 'не указан'}\n"
            f"Следующий шаг: {nxt}\nОтветственный: {lead.assignee or 'не назначен'}"
            + ("\nНужно Ваше личное участие" if lead.handoff_open else "")
        )
        rows = []
        if lead.stage not in CLOSED and not lead.assignee:
            rows.append([("✋ Взять в работу", f"sales:do:take:{lead.lead_id}")])
        main = _primary(lead)
        if main:
            rows.append([main])
        if lead.stage not in CLOSED:  # «Продажи» input flow (same /lead_note, /lead_next, /lead_assign ops)
            rows.append([("📝 Заметка", f"sales:in:note:{lead.lead_id}"),
                         ("⏰ Следующий контакт", f"sales:in:next:{lead.lead_id}")])
            rows.append([("👤 Назначить ответственного", f"sales:in:assign:{lead.lead_id}")])
        rows.append([("⋯ Ещё действия", f"cpm:sales-actions:{lead.lead_id}")])
        if lead.customer_id:
            rows.append([("👤 Карточка клиента", f"cpm:customer:{lead.customer_id[:40]}")])
        return text, rows
    if action == "sales-actions":
        lead = _lead(st, args[0] if args else "")
        if lead.stage in CLOSED:
            return f"💬 {lead.name}: обращение закрыто ({sl.LABELS[lead.stage]}). Вернуть: /lead_reopen", []
        evs = [NEXT_EVENT[lead.stage]] if lead.stage in NEXT_EVENT else []
        evs += ["paid", "declined", "resume" if lead.handoff_open else "handoff"]
        rows = [[(EVENT_LABELS[e], f"cpm:sales-ev:{lead.lead_id}:{e}")] for e in evs]
        return f"⋯ Действия: {lead.name}\n\nЗаметка: /lead_note · Следующий шаг: /lead_next", rows
    if action == "sales-recent":
        closed = [x for x in leads if x.stage in CLOSED][:7]
        lines = [f"• {x.name} · {sl.LABELS[x.stage]}" for x in closed] or ["Недавно закрытых обращений нет."]
        return "🗂 Недавно закрытые\n\n" + "\n".join(lines), [
            [(x.name[:32], f"cpm:sales-lead:{x.lead_id}")] for x in closed
        ]
    if action == "sales-handoffs":
        items = [x for x in leads if x.handoff_open][:4]
        lines = [f"{i}. {x.name} · ожидает" for i, x in enumerate(items, 1)] or [
            "Сейчас нет обращений, где требуется личное участие."
        ]
        rows = [[(f"✅ Готово {i}", f"cpm:sales-ev:{x.lead_id}:resume")] for i, x in enumerate(items, 1)]
        return "🙋 Нужно подключиться лично\n\n" + "\n".join(lines), rows
    raise ValueError(action)


def customer_leads(st: Any, customer_id: str) -> list[sl.Lead]:
    """Leads (inquiries/deals) bound to one customer, open first."""
    return [x for x in (sl.ordered(st) if st is not None else []) if customer_id and x.customer_id == customer_id]


def customer_sales_lines(leads: list[sl.Lead], *, now_ms: int) -> str:
    """Customer card block: inquiries, deal stage, owner, next action, confirmed result."""
    if not leads:
        return ""
    lines = []
    for x in leads[:4]:
        who = f" · ведёт {x.assignee}" if x.assignee else " · ответственный не назначен"
        lines.append(f"• {x.name} ({x.source or 'канал не указан'}): {sl.LABELS[x.stage]}" + ("" if x.stage in CLOSED else who))
        if x.stage == S.WON:
            lines.append("  ✅ Подтверждённый результат: оплата получена")
        elif x.stage not in CLOSED:
            late = " — просрочен" if x.due_ms and x.due_ms <= now_ms else ""
            lines.append(f"  ▶️ Следующий шаг: {x.next_action}{late}" if x.next_action else "  ▶️ Следующий шаг не задан")
        if x.notes:
            lines.append(f"  📝 {x.notes[-1][:80]}")
    return "\n\n💬 Обращения и сделки\n" + "\n".join(lines)


def customer_sales_view(st: Any, identities: list[Any], *, now_ms: int) -> list[dict[str, Any]]:
    """Web customer card: leads bound to one of the customer's verified identities (channel + subject)."""
    keys = {(str(i.get("channel") or "").strip().lower(), str(i.get("external_subject") or "").strip())
            for i in identities if isinstance(i, dict)}
    out = []
    for x in (sl.ordered(st) if st is not None else []):
        if not x.customer_id or (x.source.strip().lower(), x.customer_id) not in keys:
            continue
        out.append({
            "lead_id": x.lead_id, "name": x.name, "channel": x.source, "stage": x.stage.value,
            "stage_label": sl.LABELS[x.stage], "closed": x.stage in CLOSED, "owner": x.assignee,
            "next_action": x.next_action, "next_due_ms": x.due_ms or None,
            "overdue": bool(x.due_ms and x.due_ms <= now_ms and x.stage not in CLOSED),
            "handoff_open": x.handoff_open, "notes": list(x.notes[-5:]),
            "followup_planned_ms": x.followup_due_ms or None,
            "confirmed_result": "paid" if x.stage == S.WON else ("lost" if x.stage == S.LOST else None),
        })
    return out


def hub_markup() -> dict[str, Any]:
    """«Продажи» buttons: the same sales_pipeline ops as /leads, /lead_add, /leads_due ..."""
    rows = [
        [("📋 Все лиды", "sales:leads"), ("➕ Новый лид", "sales:in:add")],
        [("💬 Карточки и этапы", "cpm:sales")],
        [("⏰ Просроченные шаги", "sales:due"), ("🔁 Follow-up", "sales:followups")],
        [("🙋 Ждут человека", "sales:handoffs"), ("🗂 Закрытые", "sales:closed")],
        [("⬅️ Главное меню", "menu:main")],
    ]
    return {"inline_keyboard": [[{"text": t, "callback_data": c} for t, c in row] for row in rows]}


def mutation(args: tuple[str, ...], st: Any) -> dict[str, Any]:
    """Donor _sales_mutation_message: a stage button -> the same lead_event fact as /lead."""
    if len(args) != 2 or args[1] not in sl.EVENTS:
        raise ValueError("sales mutation")
    lead = _lead(st, args[0])
    return {
        "step": "lead_event",
        "lead_id": lead.lead_id,
        "event": args[1],
        "stage": sl.reduce(lead.stage, args[1]).value,
    }


def result_text(change: dict[str, Any], st: Any) -> str:
    """Donor _sales_result_message."""
    return f"✅ {_lead(st, change['lead_id']).name}: {sl.LABELS[S(change['stage'])]}"


# --- Web Sales Center (P1-18/19) ---
# Sales Center: one normalized, read-only view over the sales sources a business really has.
#
# Pure. Sources are the canonical channel pipeline (sales_pipeline@v1 facts from
# Telegram/VK/MAX inbound) and every CRM whose contacts *and* deals were confirmed
# by a live read. Nothing is written; unknown values stay ``None`` (never zero).

CANON_SALES_CENTER_VIEW = True


def _live_ok(row: Mapping[str, Any]) -> bool:
    return (str(row.get("mode") or "").lower() == "live" and row.get("accepted") is True
            and str(row.get("status") or "").lower() == "live_executed")


def latest_read(history: list[Mapping[str, Any]], operation: str) -> Mapping[str, Any] | None:
    ok = [r for r in history if isinstance(r, Mapping) and _live_ok(r) and str(r.get("operation") or "") == operation]
    return max(ok, key=lambda r: str(r.get("recorded_at_utc") or ""), default=None)


def resource_count(row: Mapping[str, Any] | None) -> int | None:
    if not row:
        return None
    for part in ("parsed_response", "transport_response"):
        value = (row.get(part) or {}).get("resource_count") if isinstance(row.get(part), Mapping) else None
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def channel_source(*, leads: Mapping[str, Any], last_fact_ms: int | None, connected_channels: list[str]) -> dict[str, Any]:
    contacts = {(getattr(x, "source", ""), getattr(x, "customer_id", "")) for x in leads.values() if getattr(x, "customer_id", "")}
    return {
        "key": "channels", "kind": "channels", "title": "Обращения из мессенджеров",
        "providers": list(connected_channels), "connected": bool(connected_channels or leads),
        "read_confirmed": bool(leads), "contacts": len(contacts) if leads else None,
        "deals": len(leads) if leads else None, "last_read_ms": last_fact_ms, "last_read_at": None,
    }


def crm_source(*, provider: Mapping[str, Any], history: list[Mapping[str, Any]]) -> dict[str, Any]:
    contacts, deals = latest_read(history, "contact_sync"), latest_read(history, "deal_sync")
    stamps = [str(r.get("recorded_at_utc") or "") for r in (contacts, deals) if r]
    return {
        "key": str(provider.get("provider_key") or ""), "kind": "crm",
        "title": str(provider.get("title") or provider.get("provider_key") or ""),
        "providers": [str(provider.get("provider_key") or "")], "connected": bool(provider.get("connected")),
        "read_confirmed": bool(contacts and deals), "contacts": resource_count(contacts),
        "deals": resource_count(deals), "last_read_ms": None, "last_read_at": min(stamps) if len(stamps) == 2 else None,
    }


def choose(sources: list[dict[str, Any]], requested: str = "") -> dict[str, Any]:
    """Canonical source: a connected CRM with confirmed contact+deal reads (system of record for
    deals), else the channel pipeline when it has leads. The owner may view another *available*
    source; an unavailable request falls back to the canonical one."""
    available = [s for s in sources if s["connected"] and s["read_confirmed"]]
    canonical = next((s for s in available if s["kind"] == "crm"), None) or next(iter(available), None)
    chosen = next((s for s in available if s["key"] == requested), canonical)
    return {
        "sources": sources, "available": [s["key"] for s in available],
        "canonical_source": canonical["key"] if canonical else None,
        "selected_source": chosen["key"] if chosen else None,
        "selection_rule": "crm_with_confirmed_contact_and_deal_reads_then_channel_pipeline",
        "write_actions_enabled": False,
    }


# --- Funnel (P1-19): one normalized stage ladder over every source ------------
STAGES = ("discovered", "engaged", "need_known", "qualified", "offer_presented", "checkout", "won")
STALE_AFTER_MS = 14 * 86_400_000
# Per-provider stage read model: provider stage key -> normalized stage (or "lost").
STAGE_MAPS: dict[str, dict[str, str]] = {
    "channels": {**{s: s for s in STAGES}, "lost": "lost"},
    "hubspot": {  # HubSpot default sales pipeline stage ids
        "appointmentscheduled": "engaged", "qualifiedtobuy": "qualified", "presentationscheduled": "offer_presented",
        "decisionmakerboughtin": "offer_presented", "contractsent": "checkout",
        "closedwon": "won", "closedlost": "lost",
    },
}


def normalize_stage(provider_key: str, stage_key: object) -> str | None:
    return STAGE_MAPS.get(provider_key, {}).get(str(stage_key or "").strip().lower())


def _funnel(reached: dict[str, int], *, won: int, lost: int, stale: int, open_: int, unmapped: int, basis: str) -> dict[str, Any]:
    conv = []
    for prev, cur in zip(STAGES, STAGES[1:], strict=False):
        base = reached.get(prev, 0)
        conv.append({"from": prev, "to": cur, "reached": reached.get(cur, 0), "base": base,
                     "rate": round(reached.get(cur, 0) / base, 4) if base else None})
    closed = won + lost
    return {"won": won, "lost": lost, "stale": stale, "open": open_, "unmapped": unmapped,
            "win_rate": round(won / closed, 4) if closed else None, "stage_conversion": conv,
            "reached": {s: reached.get(s, 0) for s in STAGES}, "basis": basis,
            "stale_after_days": STALE_AFTER_MS // 86_400_000}


def pipeline_funnel(rows: list[tuple[int, Mapping[str, Any]]], *, now_ms: int) -> dict[str, Any] | None:
    """Channel pipeline funnel from sales_pipeline@v1 facts: the highest stage each lead really reached."""
    rank = {s: i for i, s in enumerate(STAGES)}
    best: dict[str, int] = {}
    final: dict[str, str] = {}
    last: dict[str, int] = {}
    for ts, p in rows:
        lid, step = str(p.get("lead_id") or ""), p.get("step")
        if not lid:
            continue
        if step in ("lead_added", "lead_inbound"):
            best.setdefault(lid, rank["engaged"] if step == "lead_inbound" else 0)
            final.setdefault(lid, "open")
        if lid not in best:
            continue
        last[lid] = max(last.get(lid, 0), int(ts))
        if step == "lead_inbound":
            best[lid] = max(best[lid], rank["engaged"])
        elif step == "lead_event":
            stage = str(p.get("stage") or "")
            if stage == "lost":
                final[lid] = "lost"
            elif stage in rank:
                best[lid] = max(best[lid], rank[stage])
                final[lid] = "won" if stage == "won" else "open"
        elif step == "lead_reopened":
            final[lid] = "open"
    if not best:
        return None
    reached = {s: sum(1 for b in best.values() if b >= i) for i, s in enumerate(STAGES)}
    open_ids = [lid for lid, f in final.items() if f == "open"]
    return _funnel(reached, won=sum(f == "won" for f in final.values()), lost=sum(f == "lost" for f in final.values()),
                   stale=sum(1 for lid in open_ids if now_ms - last.get(lid, 0) > STALE_AFTER_MS),
                   open_=len(open_ids), unmapped=0, basis="highest_stage_reached")


def deal_funnel(deals: list[Any], *, provider_key: str, now_ms: int) -> dict[str, Any] | None:
    """CRM funnel from canonical Deal records (DealRegistry) through the provider stage map.

    Only the current stage is known, so a deal counts as having reached every stage up to it;
    lost deals count in «lost» but not in stage conversion; unmapped stages are reported, not guessed.
    """
    active = [d for d in deals if str(getattr(d, "lifecycle_status", "active")) == "active"]
    if not active:
        return None
    rank = {s: i for i, s in enumerate(STAGES)}
    reached = dict.fromkeys(STAGES, 0)
    won = lost = stale = open_ = unmapped = 0
    for d in active:
        stage = normalize_stage(provider_key, getattr(d, "stage_key", None))
        if stage is None:
            unmapped += 1
            continue
        if stage == "lost":
            lost += 1
            continue
        for s in STAGES[: rank[stage] + 1]:
            reached[s] += 1
        if stage == "won":
            won += 1
        else:
            open_ += 1
            stale += int(now_ms - int(getattr(d, "updated_at_ms", 0) or 0) > STALE_AFTER_MS)
    return _funnel(reached, won=won, lost=lost, stale=stale, open_=open_, unmapped=unmapped, basis="current_stage")


# --- Web communications center (P1-22) ---
# Web communications center (P1-22): one read-only view over existing owners.
#
# Inbound = canonical Message registry (direction inbound). Outbound / failed =
# provider sync history of ``message_send`` judged only by
# ``provider_approval_completion_truth`` (a provider receipt, never our wish).
# Queue / retries = provider queue jobs of ``message_send`` (attempts > 0 is a
# retry). Pending approvals stay with the existing approvals API. No writes, no
# sender, no second decision owner.

CANON_COMMUNICATIONS_CENTER = True
COMMS_LIMIT = 50


def inbound_rows(messages: Iterable[Any]) -> list[dict[str, Any]]:
    rows = [{"message_id": m.message_id, "channel": m.channel, "customer_id": m.customer_id or "",
             "conversation_id": m.conversation_id or "", "at_ms": int(m.created_at_ms or 0)}
            for m in messages if str(getattr(m.direction, "value", m.direction)) == "inbound"]
    return sorted(rows, key=lambda r: -r["at_ms"])[:COMMS_LIMIT]


def outbound_rows(provider_key: str, history: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    from application.business_autonomy.provider_delivery_truth import provider_approval_completion_truth

    out = []
    for row in history:
        if str(row.get("operation") or "") != "message_send" or str(row.get("mode") or "live") != "live":
            continue
        delivered, ambiguous, terminal = provider_approval_completion_truth(provider_key=provider_key, result=row)
        error = dict(row.get("error") or {})
        out.append({
            "provider_key": provider_key,
            "state": "delivered" if delivered else "failed" if terminal else "unconfirmed",
            "receipt": str(dict(row.get("parsed_response") or {}).get("resource_id") or "") if delivered else "",
            "reason": "" if delivered else str(error.get("category") or row.get("status") or ""),
            "at": str(row.get("recorded_at_utc") or ""),
            "queue_job_id": str(row.get("queue_job_id") or ""),
        })
    return out


def queue_rows(provider_key: str, jobs: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for job in jobs:
        payload = dict(job.get("payload") or {})
        if str(payload.get("operation") or "") != "message_send" or str(job.get("state") or "") not in {"pending", "claimed"}:
            continue
        out.append({"provider_key": provider_key, "job_id": str(job.get("job_id") or ""),
                    "attempts": int(job.get("attempts") or 0), "run_at": str(job.get("run_at") or "")})
    return out


def communications_view(*, messages: Iterable[Any], providers: Mapping[str, tuple[Iterable[Mapping[str, Any]], Iterable[Mapping[str, Any]]]]) -> dict[str, Any]:
    """``providers``: provider_key -> (sync history rows, queue jobs)."""
    outbound, queued = [], []
    for key, (history, jobs) in sorted(providers.items()):
        outbound += outbound_rows(key, history)
        queued += queue_rows(key, jobs)
    outbound.sort(key=lambda r: r["at"], reverse=True)
    view = {
        "inbound": inbound_rows(messages),
        "outbound": [r for r in outbound if r["state"] == "delivered"][:COMMS_LIMIT],
        "unconfirmed": [r for r in outbound if r["state"] == "unconfirmed"][:COMMS_LIMIT],
        "failed": [r for r in outbound if r["state"] == "failed"][:COMMS_LIMIT],
        "queued": [r for r in queued if r["attempts"] == 0][:COMMS_LIMIT],
        "retries": [r for r in queued if r["attempts"] > 0][:COMMS_LIMIT],
        "pending_approval_source": "/control-plane/approvals/open",
    }
    view["counts"] = {k: len(v) for k, v in view.items() if isinstance(v, list)}
    return view


__all__ = ["CANON_COCKPIT_SALES", "PARENTS", "SCREENS", "customer_leads", "customer_sales_lines", "customer_sales_view", "hub_markup", "mutation", "result_text", "screen",
           "CANON_SALES_CENTER_VIEW", "STAGE_MAPS", "deal_funnel", "normalize_stage", "pipeline_funnel", "channel_source", "choose",
           "crm_source", "latest_read", "resource_count",
           "CANON_COMMUNICATIONS_CENTER", "COMMS_LIMIT", "communications_view", "inbound_rows", "outbound_rows", "queue_rows"]
