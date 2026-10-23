"""Slot promotions with first-party attribution (port of donor ``promotions`` + ``promotion_creatives``).

Pure and deterministic: copy is built from owner facts only (business activity, offering, slot time),
filtered through the donor guardrails, and never published externally. A campaign is one
(slot, channel) pair with an unguessable source token; ``/start cpa_<token>`` records an ``opened``
touch for that customer and ``/promo_book <token>`` books the slot with the campaign attribution in
the same ``booked`` fact. Re-promoting the same slot+channel refreshes the creative, keeping the token.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from application.business_flows import messenger_switching as ms

CANON_PROMOTIONS = True
PREFIX = "cpa_"
PUBLIC_PATH = "/clientplatform/acquire"
CHANNELS = ("telegram", "vk", "max", "whatsapp", "website", "offline")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{12,32}")
_PUNCT = re.compile(r"([!?])\1\1+")
SHAMING = ("стыдно", "позор", "ты виноват", "ты плохой", "ленивый", "слабак")
MEDICAL = ("вылечим", "гарантированно вылечит", "исцеляет", "без побочных эффектов", "избавим навсегда")
DENY = ("100% гарантия", "лучший в мире", "гарантированный результат")
_CONSULT = ("психолог", "психотерап", "консультац", "коуч", "настав", "преподав", "заняти", "терап")
_LOCAL = ("сантех", "ремонт", "установ", "мастер", "автосервис", "автослес", "электрик", "окн", "уборк")


def normalize_token(value: object) -> str:
    v = str(value or "").strip()
    if not _TOKEN.fullmatch(v):
        raise ValueError("неверный код промо-ссылки")
    return v


def start_payload(token: str) -> str:
    return PREFIX + normalize_token(token)


def parse_start_payload(payload: str) -> str | None:
    raw = str(payload or "").strip()
    if not raw.startswith(PREFIX):
        return None
    try:
        return normalize_token(raw.removeprefix(PREFIX))
    except ValueError:
        return None


def public_url(base_url: str, token: str) -> str:
    """Channel-neutral HTTPS acquisition URL (donor ``build_public_promotion_url``)."""
    p = urlsplit(str(base_url or "").strip())
    if p.scheme != "https" or not p.hostname:
        raise ValueError("адрес лендинга должен быть HTTPS")
    if p.query or p.fragment:
        raise ValueError("адрес лендинга без query и fragment")
    q = "source=" + normalize_token(token)  # token charset [A-Za-z0-9_-] needs no escaping
    return urlunsplit(("https", p.netloc, p.path.rstrip("/") + PUBLIC_PATH, q, ""))


@dataclass(frozen=True)
class Creative:
    creative_id: str
    headline: str
    primary_text: str
    description: str
    cta: str = "Записаться"
    style: str = "direct"


@dataclass(frozen=True)
class Brief:
    business_name: str
    activity: str
    offering_title: str
    offering_description: str
    local_start: str
    duration_min: int


def _compact(v: object, n: int) -> str:
    return " ".join(str(v or "").split())[:n].rstrip()


def _caps(v: str) -> bool:
    letters = [c for c in v if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def validate(c: Creative) -> tuple[bool, str]:
    if len(c.headline) > 60:
        return False, "headline_too_long"
    if len(c.primary_text) > 420:
        return False, "primary_text_too_long"
    if len(c.description) > 100:
        return False, "description_too_long"
    text = " ".join((c.headline, c.primary_text, c.description)).strip()
    low = text.lower()
    if _caps(c.headline) or _caps(c.primary_text):
        return False, "all_caps_disallowed"
    if _PUNCT.search(text):
        return False, "excessive_punctuation"
    if any(p in low for p in SHAMING):
        return False, "shaming_language"
    if any(p in low for p in MEDICAL):
        return False, "medical_claims"
    if any(p in low for p in DENY):
        return False, "deny_phrase"
    return True, "ok"


def _cand(b: Brief, style: str, headline: str, primary: str, desc: str) -> Creative:
    h, p, d = _compact(headline, 60), _compact(primary, 420), _compact(desc, 100)
    parts = (b.business_name, b.offering_title, b.local_start, b.duration_min, style, h, p)
    cid = "cr_" + hashlib.sha256("||".join(str(x or "").strip() for x in parts).encode()).hexdigest()[:16]
    return Creative(cid, h, p, d, "Записаться", style)


def _kind(b: Brief) -> str:
    ctx = " ".join((b.business_name, b.activity, b.offering_title, b.offering_description)).lower()
    if any(m in ctx for m in _CONSULT):
        return "consultation"
    return "local_service" if any(m in ctx for m in _LOCAL) else "general"


def candidates(b: Brief) -> list[Creative]:
    """Three domain-aware variants (donor ``generate_promotion_candidates``); unsafe ones dropped."""
    details = _compact(b.offering_description or b.activity, 190) or "Онлайн-запись на удобное время"
    biz, off, when, mins = (
        _compact(b.business_name, 80) or "нашей команды",
        _compact(b.offering_title, 100),
        _compact(b.local_start, 40),
        b.duration_min,
    )
    kind = _kind(b)
    if kind == "consultation":
        vs = [
            _cand(
                b,
                "trust",
                off,
                f"{details}. Доступно время: {when}. Можно спокойно посмотреть формат встречи и записаться онлайн.",
                f"{mins} минут · {biz}",
            ),
            _cand(
                b,
                "expert",
                f"Встреча с {biz}",
                f"{off}. {details}. Ближайшее свободное время — {when}.",
                "Выберите удобное время без переписки",
            ),
            _cand(b, "concise", f"Свободное время: {off}", f"{when}, {mins} минут. Запись онлайн.", biz),
        ]
    elif kind == "local_service":
        vs = [
            _cand(
                b,
                "availability",
                f"Свободное время: {off}",
                f"{biz}. {details}. Можно записаться на {when}. Откройте карточку и подтвердите время.",
                f"{mins} минут · запись онлайн",
            ),
            _cand(
                b,
                "service",
                off,
                f"{details}. Доступное время: {when}. Запишитесь напрямую без звонков и ожидания ответа.",
                biz,
            ),
            _cand(
                b,
                "concise",
                f"{off} · {when}",
                f"Свободное время у {biz}. Нажмите, чтобы записаться.",
                f"Продолжительность: {mins} минут",
            ),
        ]
    else:
        vs = [
            _cand(
                b,
                "direct",
                off,
                f"{details}. Свободное время: {when}. Посмотрите подробности и запишитесь онлайн.",
                f"{mins} минут · {biz}",
            ),
            _cand(
                b,
                "business",
                f"Предложение от {biz}",
                f"{off}. {details}. Доступно: {when}.",
                "Прямая запись без лишней переписки",
            ),
            _cand(b, "concise", f"Свободно: {off}", f"{when}, {mins} минут. Записаться онлайн.", biz),
        ]
    safe = [c for c in vs if validate(c)[0]]
    if safe:
        return safe
    fb = _cand(
        b,
        "fallback",
        _compact(b.offering_title, 60) or "Запись на услугу",
        f"Доступно время: {b.local_start}. Посмотрите подробности и запишитесь на удобное время.",
        f"{mins} минут · запись онлайн",
    )
    if validate(fb)[0]:
        return [fb]
    return [
        _cand(
            b,
            "fixed_safe_fallback",
            "Запись на услугу",
            f"Доступно время: {when}. Посмотрите подробности и запишитесь онлайн.",
            f"Продолжительность: {mins} минут",
        )
    ]


def _score(c: Creative) -> float:
    s = 0.1 + (0.05 if 10 <= len(c.headline) <= 45 else 0)
    low = (c.primary_text + " " + c.description).lower()
    s += 0.05 if any(m in low for m in ("запис", "консультац", "встреч", "услуг", "время")) else 0
    return s + (0.02 if "!" not in low else 0)


def best_creative(cands: list[Creative]) -> Creative:
    valid = [c for c in cands if validate(c)[0]]
    if not valid:
        raise ValueError("нет безопасного варианта текста")
    return max(valid, key=lambda c: (_score(c), c.creative_id))


@dataclass
class Campaign:
    campaign_id: str
    slot_id: str
    channel: str
    token: str
    creative: Creative
    opened: set[str] = field(default_factory=set)
    booked: set[str] = field(default_factory=set)


def replay(payloads: list[dict[str, Any]]) -> dict[str, Campaign]:
    """Campaigns from bookings@v1 facts; ``booked`` facts carrying ``promotion_id`` attribute bookings."""
    out: dict[str, Campaign] = {}
    for p in payloads:
        step, cid = p.get("step"), str(p.get("promotion_id") or "")
        if step == "promotion_saved":
            cr = Creative(**p["creative"])
            if cid in out:
                out[cid].creative = cr
            else:
                out[cid] = Campaign(cid, p["slot_id"], p["channel"], p["source_token"], cr)
        elif cid in out and step == "promotion_opened":
            out[cid].opened.add(str(p.get("customer_id") or ""))
        elif cid in out and step == "booked":  # a promoted booking implies an opened touch (donor records both)
            out[cid].opened.add(str(p.get("customer_id") or ""))
            out[cid].booked.add(str(p.get("customer_id") or ""))
    return out


def by_token(camps: dict[str, Campaign], token: str) -> Campaign:
    t = normalize_token(token)
    for c in camps.values():
        if c.token == t:
            return c
    raise ValueError("промо-ссылка не найдена")


def save(camps: dict[str, Campaign], *, slot_id: str, channel: str, brief: Brief, new_token: str) -> dict[str, Any]:
    """Create or refresh the (slot, channel) campaign (donor ``create_or_refresh_campaign``)."""
    ch = str(channel or "telegram").strip().lower()
    if ch not in CHANNELS:
        raise ValueError("канал: " + ", ".join(CHANNELS))
    existing = next((c for c in camps.values() if c.slot_id == slot_id and c.channel == ch), None)
    token = existing.token if existing else normalize_token(new_token)
    cid = existing.campaign_id if existing else "pr_" + hashlib.sha256(f"{slot_id}:{ch}".encode()).hexdigest()[:12]
    cr = best_creative(candidates(brief))
    return {
        "step": "promotion_saved",
        "promotion_id": cid,
        "slot_id": slot_id,
        "channel": ch,
        "source_token": token,
        "creative": cr.__dict__,
    }


def opened_fact(c: Campaign, customer_id: str) -> dict[str, Any] | None:
    """One ``opened`` touch per customer per campaign (repeat opens add nothing)."""
    if customer_id in c.opened:
        return None
    return {
        "step": "promotion_opened",
        "promotion_id": c.campaign_id,
        "slot_id": c.slot_id,
        "customer_id": customer_id,
        "source_token": c.token,
    }


def card(c: Campaign, slot_line: str) -> str:
    cr = c.creative
    return f"📣 {cr.headline}\n\n{cr.primary_text}\n{cr.description}\n\n🗓 {slot_line}\n{cr.cta}: /promo_book {c.token}"


def stats_text(camps: dict[str, Campaign], slot_line) -> str:
    if not camps:
        return "📣 Промо-кампаний нет. Создать: /promote N [канал] (N из /slots)"
    lines = ["📣 Промо-кампании"]
    for i, c in enumerate(camps.values(), 1):
        o, b = len(c.opened), len(c.booked)
        conv = f"{round(100 * b / o)}%" if o else "—"
        lines.append(
            f"{i}. [{c.channel}] {c.creative.headline} · {slot_line(c.slot_id)}\n   открыли {o} · записались {b} · конверсия {conv}\n   ссылка: /start {PREFIX}{c.token}"
        )
    return "\n".join(lines)


def open_channel(
    camps: dict[str, Campaign], token: str, *, customer_id: str, active_customers: set[str]
) -> tuple[Campaign, dict[str, Any] | None]:
    """Verified touch for an existing channel customer (donor ``open_channel_promotion``)."""
    camp = by_token(camps, token)  # campaigns are replayed per tenant, so a foreign token never resolves
    if customer_id not in active_customers:
        raise ValueError("атрибуция промо требует активного клиента этого бизнеса")
    return camp, opened_fact(camp, customer_id)


def open_channel_for_identity(
    camps: dict[str, Campaign],
    token: str,
    *,
    platform: str,
    external_subject: str,
    identities: dict[tuple[str, str], str],
) -> tuple[Campaign, dict[str, Any] | None]:
    """Resolve an active channel identity first (donor ``open_channel_promotion_for_identity``)."""
    key = (str(platform or "").strip().lower(), str(external_subject or "").strip())
    customer_id = identities.get(key)
    if not key[1] or customer_id is None:
        raise ValueError("атрибуция промо требует активной идентичности клиента в канале")
    return open_channel(camps, token, customer_id=customer_id, active_customers={customer_id})


@dataclass(frozen=True)
class Destination:
    """Donor acquisition_destination: channel-neutral URL + native messenger deep links for one token."""

    campaign_id: str
    source_token: str
    public_url: str | None
    messengers: tuple[ms.PublicDestination, ...]

    @property
    def has_native_messenger(self) -> bool:
        return bool(self.messengers)


def acquisition_destination(campaign: Any, *, base_url: str = "", bots: Iterable[Any] = (),
          connections: Iterable[Mapping[str, Any]] = ()) -> Destination:  # fmt: skip
    token = normalize_token(campaign.token)
    try:
        url = public_url(base_url, token) if str(base_url or "").strip() else None
    except ValueError:
        url = None  # misconfigured base URL never blocks messenger links
    links = ms.public_destinations(start_payload(token), bots=list(bots), connections=list(connections))
    return Destination(str(campaign.campaign_id), token, url, links)


def resolve_destination(camps: Mapping[str, Any], token: str, **kw: Any) -> Destination:
    """Donor resolve_acquisition_destination: public source token -> the same destination."""
    return acquisition_destination(by_token(dict(camps), token), **kw)


def nearest_open_slot(slots: Iterable[Any], *, offering_ids: Mapping[str, str] | None = None,
                 offering_id: str = "") -> Any | None:  # fmt: skip
    """Donor prepare_nearest_acquisition_destination slot choice: earliest open slot (optionally of one offering)."""
    pool = [s for s in slots if not offering_id or (offering_ids or {}).get(s.slot_id) == offering_id]
    return min(pool, key=lambda s: s.starts_at_ms) if pool else None


_LABEL = {"telegram": "Telegram", "vk": "ВКонтакте", "max": "MAX"}


def destination_lines(d: Destination) -> list[str]:
    out = [f"🌐 {d.public_url}"] if d.public_url else []
    out += [f"💬 {_LABEL.get(m.platform, m.platform)}: {m.url}" for m in d.messengers]
    return out
