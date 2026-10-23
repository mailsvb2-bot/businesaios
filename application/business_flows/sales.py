"""Owner sales pipeline: leads, conversation stage, next action, notes, human handoff.

Port of clientplatform ``sales_state_machine`` / ``sales_operations`` / ``sales_workspace`` /
``sales_handoff`` / ``sales_metrics`` onto ``sales_pipeline@v1`` facts. Stage names reuse the
canonical ``advisory.funnel_intelligence.contracts.DerivedConversationStage``; the reducer is
the donor's: monotonic one-step progress, payment wins, decline/disqualify loses, handoff
signals never rewind the funnel. Nothing here messages a customer.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from advisory.funnel_intelligence.contracts import DerivedConversationStage as Stage
from application.business_flows.projection import stable_id

CANON_SALES_PIPELINE_FLOW = True
RANK = {
    s: i
    for i, s in enumerate(
        (
            Stage.DISCOVERED,
            Stage.ENGAGED,
            Stage.NEED_KNOWN,
            Stage.QUALIFIED,
            Stage.OFFER_PRESENTED,
            Stage.CHECKOUT,
            Stage.WON,
        )
    )
}
TARGETS = {
    "contact": Stage.ENGAGED,
    "need": Stage.NEED_KNOWN,
    "qualified": Stage.QUALIFIED,
    "offer": Stage.OFFER_PRESENTED,
    "checkout": Stage.CHECKOUT,
}
LABELS = {
    Stage.DISCOVERED: "новый",
    Stage.ENGAGED: "на связи",
    Stage.NEED_KNOWN: "потребность ясна",
    Stage.QUALIFIED: "подходит",
    Stage.OFFER_PRESENTED: "предложение сделано",
    Stage.CHECKOUT: "оплачивает",
    Stage.WON: "купил",
    Stage.LOST: "отказ",
}
EVENTS = (*TARGETS, "paid", "declined", "disqualified", "handoff", "resume")


@dataclass(frozen=True)
class Lead:
    lead_id: str
    name: str
    source: str = ""
    stage: Stage = Stage.DISCOVERED
    next_action: str = ""
    due_ms: int = 0
    notes: tuple[str, ...] = ()
    handoff_open: bool = False
    customer_id: str = ""
    followup_id: str = ""
    followup_due_ms: int = 0
    followup_text: str = ""
    followup_suppressed: bool = False


@dataclass
class State:
    leads: dict[str, Lead] = field(default_factory=dict)


def reduce(current: Stage, event: str) -> Stage:
    """Donor reducer semantics (sales_state_machine.reduce_sales_conversation)."""
    if event in ("handoff", "resume"):
        return current
    if event == "paid":
        return Stage.WON
    if current == Stage.WON:
        return current
    if event in ("declined", "disqualified"):
        return Stage.LOST
    if current == Stage.LOST:
        raise ValueError("lead_closed: откройте заново /lead_reopen N")
    target = TARGETS.get(event)
    if target is None:
        raise ValueError("lead_event_unknown: " + ", ".join(EVENTS))
    if RANK[current] >= RANK[target]:
        return current
    if RANK[target] != RANK[current] + 1:
        raise ValueError(f"stage_skip_not_allowed: {LABELS[current]} → {LABELS[target]}")
    return target


def replay(payloads: list[dict[str, Any]]) -> State:
    st = State()
    for p in payloads:
        step, lid = p.get("step"), str(p.get("lead_id") or "")
        lead = st.leads.get(lid)
        if step == "lead_added":
            st.leads[lid] = Lead(lid, p["name"], p.get("source", ""))
        elif step == "lead_inbound":  # sales_inbound.record_message
            lead = lead or Lead(lid, p["name"], p.get("source", ""))
            stage = Stage.ENGAGED if lead.stage == Stage.DISCOVERED else lead.stage
            notes = (*lead.notes, p["note"])[-20:] if p.get("note") else lead.notes
            # donor SalesFollowupRepository.stop_for_inbound: a reply cancels the pending follow-up
            st.leads[lid] = replace(
                lead,
                stage=stage,
                notes=notes,
                customer_id=str(p.get("customer_id") or lead.customer_id),
                followup_id="",
                followup_due_ms=0,
                followup_text="",
            )
        elif lead is None:
            continue
        elif step == "followup_planned":
            st.leads[lid] = replace(
                lead, followup_id=p["followup_id"], followup_due_ms=int(p["due_ms"]), followup_text=p["text"]
            )
        elif step in ("followup_cancelled", "followup_sent") and lead.followup_id == p.get("followup_id"):
            st.leads[lid] = replace(lead, followup_id="", followup_due_ms=0, followup_text="")
        elif step == "followup_optout":
            st.leads[lid] = replace(lead, followup_suppressed=True, followup_id="", followup_due_ms=0, followup_text="")
        elif step == "lead_event":
            st.leads[lid] = replace(
                lead,
                stage=Stage(p["stage"]),
                handoff_open=(p["event"] == "handoff") or (lead.handoff_open and p["event"] != "resume"),
            )
        elif step == "lead_reopened":
            st.leads[lid] = replace(lead, stage=Stage.ENGAGED)
        elif step == "lead_next":
            st.leads[lid] = replace(lead, next_action=p["text"], due_ms=int(p["due_ms"]))
        elif step == "lead_note":
            st.leads[lid] = replace(lead, notes=(*lead.notes, p["text"])[-20:])
    return st


def ordered(st: State) -> list[Lead]:
    return sorted(st.leads.values(), key=lambda x: (x.stage in (Stage.WON, Stage.LOST), x.lead_id))


def pick(st: State, ref: str) -> Lead:
    leads = ordered(st)
    if not ref.isdigit() or not 0 < int(ref) <= len(leads):
        raise ValueError("lead_number_unknown: /leads")
    return leads[int(ref) - 1]


def add_lead(arg: str) -> dict[str, Any]:
    name, _, source = (x.strip() for x in str(arg or "").partition("|"))
    if not name:
        raise ValueError("lead_format: /lead_add Имя | источник")
    return {
        "step": "lead_added",
        "lead_id": stable_id("lead", name.casefold(), source.casefold()),
        "name": name[:80],
        "source": source[:60],
    }


def apply_event(st: State, arg: str) -> dict[str, Any]:
    ref, _, event = str(arg or "").strip().partition(" ")
    lead, event = pick(st, ref), event.strip().casefold()
    if event not in EVENTS:
        raise ValueError("lead_event_unknown: " + ", ".join(EVENTS))
    return {"step": "lead_event", "lead_id": lead.lead_id, "event": event, "stage": reduce(lead.stage, event).value}


def reopen(st: State, ref: str) -> dict[str, Any]:
    lead = pick(st, ref.strip())
    if lead.stage != Stage.LOST:
        raise ValueError("lead_not_lost")
    return {"step": "lead_reopened", "lead_id": lead.lead_id}


def set_next(st: State, arg: str, *, now_ms: int, tz: str = "Europe/Moscow") -> dict[str, Any]:
    parts = [x.strip() for x in str(arg or "").split("|")]
    if len(parts) != 3 or not parts[2]:
        raise ValueError("next_format: /lead_next N | 2027-01-20 10:00 | позвонить")
    lead = pick(st, parts[0])
    try:
        due = int(datetime.strptime(parts[1], "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz)).timestamp() * 1000)
    except ValueError as exc:
        raise ValueError("next_datetime_invalid") from exc
    if due <= now_ms:
        raise ValueError("next_in_past")
    return {"step": "lead_next", "lead_id": lead.lead_id, "text": parts[2][:200], "due_ms": due}


def add_note(st: State, arg: str) -> dict[str, Any]:
    ref, _, text = (x.strip() for x in str(arg or "").partition("|"))
    if not text:
        raise ValueError("note_format: /lead_note N | текст")
    return {"step": "lead_note", "lead_id": pick(st, ref).lead_id, "text": text[:300]}


def funnel(st: State) -> dict[str, int]:
    out = {LABELS[s]: 0 for s in LABELS}
    for lead in st.leads.values():
        out[LABELS[lead.stage]] += 1
    return out


def due_actions(st: State, *, now_ms: int) -> list[Lead]:
    return [x for x in ordered(st) if x.next_action and x.due_ms <= now_ms and x.stage not in (Stage.WON, Stage.LOST)]


def render(st: State, *, now_ms: int) -> str:
    rows = []
    for i, x in enumerate(ordered(st), 1):
        flag = " 🙋 нужен человек" if x.handoff_open else ""
        due = " ⏰" if x in due_actions(st, now_ms=now_ms) else ""
        nxt = f" · дальше: {x.next_action}{due}" if x.next_action else ""
        rows.append(f"{i}. {x.name} — {LABELS[x.stage]}{flag}{nxt}")
    body = "\n".join(rows) or "Лидов нет. Добавить: /lead_add Имя | источник"
    counts = ", ".join(f"{k}: {v}" for k, v in funnel(st).items() if v)
    return "🎯 Продажи\n\n" + body + (f"\n\nВоронка: {counts}" if counts else "")


__all__ = [
    "CANON_SALES_PIPELINE_FLOW",
    "Lead",
    "State",
    "add_lead",
    "add_note",
    "apply_event",
    "due_actions",
    "funnel",
    "ordered",
    "pick",
    "reduce",
    "render",
    "reopen",
    "replay",
    "set_next",
]
