"""Ad unit economics (port of clientplatform ``yandex_growth_analytics`` metric math).

Provider reports are not pulled (no live Direct connector): the owner enters cumulative
numbers from the Direct cabinet via ``/ad_stats N | показы | клики | расход RUB``. Local
attribution: leads whose source is ``adN`` (``/lead_add Имя | ad1``); bookings are leads that
reached checkout/won, customers are won. Undefined ratios are shown as «—», never as 0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.business_flows import admin as ad
from application.business_flows.ad_proposals import AdDraft, by_ref
from application.business_flows.sales import Lead, Stage

BOOKED = frozenset({Stage.CHECKOUT, Stage.WON})


@dataclass(frozen=True)
class Stats:
    impressions: int
    clicks: int
    cost_minor: int
    currency: str


def replay(payloads: list[dict[str, Any]]) -> dict[str, Stats]:
    out: dict[str, Stats] = {}
    for p in payloads:
        if p.get("step") == "ad_stats_recorded":
            out[p["draft_id"]] = Stats(int(p["impressions"]), int(p["clicks"]), int(p["cost_minor"]), p["currency"])
    return out


def record(drafts: dict[str, AdDraft], arg: str) -> dict[str, Any]:
    parts = [x.strip() for x in str(arg or "").split("|")]
    if len(parts) != 4 or not parts[1].isdigit() or not parts[2].isdigit():
        raise ValueError("формат: /ad_stats N | показы | клики | расход RUB")
    d = by_ref(drafts, parts[0])
    imp, clicks = int(parts[1]), int(parts[2])
    if clicks > imp:
        raise ValueError("кликов больше, чем показов")
    cost, cur = ad.parse_money(parts[3]) if parts[3] not in {"0", "0 RUB"} else (0, "RUB")
    return {
        "step": "ad_stats_recorded",
        "draft_id": d.draft_id,
        "impressions": imp,
        "clicks": clicks,
        "cost_minor": cost,
        "currency": cur,
    }


def percent(num: int, den: int) -> str:
    return f"{num * 100 / den:.2f}%" if den else "—"


def unit_cost(cost_minor: int, n: int, currency: str) -> str:
    return ad.money(round(cost_minor / n), currency) if n else "—"


def attribution(leads: list[Lead], n: int) -> tuple[int, int, int]:
    mine = [lead for lead in leads if lead.source.casefold() == f"ad{n}"]
    return len(mine), sum(lead.stage in BOOKED for lead in mine), sum(lead.stage == Stage.WON for lead in mine)


def report(drafts: dict[str, AdDraft], stats: dict[str, Stats], leads: list[Lead]) -> str:
    rows = []
    for n, d in enumerate(drafts.values(), 1):
        s = stats.get(d.draft_id)
        if s is None:
            continue
        nl, nb, nw = attribution(leads, n)
        rows.append(
            f"{n}. {d.title}: показы {s.impressions}, клики {s.clicks}, CTR {percent(s.clicks, s.impressions)}, "
            f"расход {ad.money(s.cost_minor, s.currency)}\n   CPC {unit_cost(s.cost_minor, s.clicks, s.currency)} · "
            f"лиды {nl}, CPL {unit_cost(s.cost_minor, nl, s.currency)} · записи {nb}, "
            f"стоимость записи {unit_cost(s.cost_minor, nb, s.currency)} · клиенты {nw}, CAC {unit_cost(s.cost_minor, nw, s.currency)}"
        )
    return "📈 Экономика рекламы (данные вводите из кабинета Директа)\n" + (
        "\n".join(rows) or "Нет данных. /ad_stats N | показы | клики | расход RUB"
    )
