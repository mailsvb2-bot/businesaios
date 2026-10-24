"""Retention cohorts and owner-approved reactivation (port of clientplatform ``retention``).

Read-only cohort projection over booking facts; ``/reactivate N`` only materialises a sales
lead (source ``reactivation:<cohort>``). It never queues or sends a customer message — any
outreach stays behind the follow-up / approval boundary. Repeat payment is recorded via the
normal ``/lead N paid`` + ``/pay`` path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.business_flows.projection import stable_id
from application.business_flows.sales import Stage, State

DAY_MS = 86_400_000
COHORTS = {"repeat": "постоянный клиент пропал", "winback": "был один раз"}


@dataclass(frozen=True)
class Candidate:
    customer_id: str
    cohort: str
    visits: int
    last_ms: int
    inactive_days: int

    @property
    def next_action(self) -> str:  # donor _next_action
        if self.cohort == "repeat":
            return "Подготовить повторное предложение для клиента"
        return "Подготовить предложение для возврата клиента"


def candidates(slots: dict[str, Any], *, now_ms: int, inactive_days: int = 45) -> list[Candidate]:
    seen: dict[str, list[int]] = {}
    future: set[str] = set()
    for s in slots.values():
        if not s.customer_id or s.status != "booked":
            continue
        if s.starts_at_ms > now_ms:
            future.add(s.customer_id)
        else:
            seen.setdefault(s.customer_id, []).append(s.starts_at_ms)
    out = []
    for cid, times in seen.items():
        idle = (now_ms - max(times)) // DAY_MS
        if cid in future or idle < inactive_days:
            continue
        out.append(Candidate(cid, "repeat" if len(times) > 1 else "winback", len(times), max(times), int(idle)))
    return sorted(out, key=lambda c: (-c.visits, -c.inactive_days, c.customer_id))


def lead_id_for(c: Candidate) -> str:
    return stable_id("lead", f"reactivation:{c.customer_id}:{c.last_ms}")


def prepare(sales: State, cands: list[Candidate], ref: str) -> tuple[dict[str, Any] | None, Candidate]:
    """-> (lead_added fact or None if this cycle already exists, candidate). Won cycle fails closed."""
    ref = str(ref or "").strip()
    if not (ref.isdigit() and 0 < int(ref) <= len(cands)):
        raise ValueError("кандидат не найден или список изменился — /retention")
    c = cands[int(ref) - 1]
    lid = lead_id_for(c)
    existing = sales.leads.get(lid)
    if existing is not None:
        if existing.stage == Stage.WON:
            raise ValueError("этот цикл возврата уже завершён оплатой")
        return None, c
    fact = {
        "step": "lead_added",
        "lead_id": lid,
        "name": f"Возврат: {c.customer_id}"[:80],
        "source": f"reactivation:{c.cohort}",
    }
    return fact, c


def text(cands: list[Candidate], sales: State, *, inactive_days: int) -> str:
    rows = []
    for i, c in enumerate(cands, 1):
        mark = " · лид создан" if lead_id_for(c) in sales.leads else ""
        rows.append(f"{i}. {c.customer_id} — {COHORTS[c.cohort]}, визитов {c.visits}, нет {c.inactive_days} дн.{mark}")
    return (
        f"🔁 Клиенты для возврата (нет визитов ≥ {inactive_days} дн., без будущих записей)\n"
        + ("\n".join(rows) or "Таких клиентов нет.")
        + "\n\n/reactivate N — создать лид (сообщения сами не отправляются)"
    )
