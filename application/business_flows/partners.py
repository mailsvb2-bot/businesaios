"""Partner search: owner-curated candidates ranked against an audience goal.

Ported from clientplatform ``partner_scoring`` (explainable 0..100 score).
Advisory only: nothing here contacts a partner; first contact needs a lawful
basis (opted-in or existing relationship), public contacts only prepare a proposal.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from html import escape
from typing import Any

from application.business_flows.projection import stable_id

CONTACTABILITY = {"opted_in": 100.0, "existing": 95.0, "public": 82.0, "unknown": 20.0, "none": 0.0}
FIRST_CONTACT_OK = frozenset({"opted_in", "existing"})


@dataclass(frozen=True)
class Partner:
    partner_id: str
    name: str
    tags: tuple[str, ...]
    followers: int | None
    basis: str
    contact: str
    competitor: bool = False


@dataclass(frozen=True)
class Fit:
    partner: Partner
    total: float
    reasons: tuple[str, ...]


def parse_partner(arg: str) -> dict[str, Any]:
    """``Имя | теги, через, запятую | подписчики | opted_in|existing|public|unknown | контакт [| competitor]``."""
    parts = [p.strip() for p in str(arg or "").split("|")]
    if len(parts) < 4 or not parts[0]:
        raise ValueError("partner_format: /partner_add Имя | теги | подписчики | основание | контакт")
    basis = parts[3].casefold()
    if basis not in CONTACTABILITY:
        raise ValueError("partner_contact_basis_invalid")
    followers = int(parts[2]) if parts[2].isdigit() else None
    return {
        "step": "partner_added",
        "partner_id": stable_id("partner", parts[0].casefold()),
        "name": parts[0][:120],
        "tags": [t.strip()[:40] for t in parts[1].split(",") if t.strip()][:12],
        "followers": followers,
        "basis": basis,
        "contact": (parts[4] if len(parts) > 4 else "")[:200],
        "competitor": len(parts) > 5 and parts[5].casefold() == "competitor",
    }


def replay(payloads: list[dict[str, Any]]) -> dict[str, Partner]:
    out: dict[str, Partner] = {}
    for p in payloads:
        if p.get("step") == "partner_added":
            out[str(p["partner_id"])] = Partner(
                str(p["partner_id"]),
                str(p["name"]),
                tuple(p.get("tags") or ()),
                p.get("followers"),
                str(p["basis"]),
                str(p.get("contact") or ""),
                bool(p.get("competitor")),
            )
        elif p.get("step") == "partner_removed":
            out.pop(str(p.get("partner_id")), None)
    return out


STATUSES = {
    "new": "новый",
    "prepared": "предложение готово",
    "contacted": "связались",
    "replied": "ответил",
    "agreed": "договорились",
    "declined": "отказ",
}
_NEXT = {
    "new": {"prepared", "declined"},
    "prepared": {"contacted", "declined"},
    "contacted": {"replied", "declined"},
    "replied": {"agreed", "declined"},
    "agreed": set(),
    "declined": {"new"},
}
_DENY = (
    "100% гарантия",
    "гарантированный результат",
    "избавим навсегда",
    "вылечим",
    "исцеляет",
    "без побочных эффектов",
)
_FAKE_FAMILIARITY = ("мы изучили ваш канал", "давно слежу")


def statuses(payloads: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in payloads:
        if p.get("step") == "partner_status":
            out[str(p["partner_id"])] = str(p["status"])
    return out


def set_status(partner: Partner | None, current: str, status: str) -> dict[str, Any]:
    """Candidate pipeline (ported from partner_runtime.set_partner_candidate_status); contact stays manual."""
    if partner is None:
        raise ValueError("partner_not_found")
    if status not in STATUSES or status not in _NEXT.get(current or "new", set()):
        raise ValueError(f"partner_status_invalid:{current or 'new'}->{status}")
    return {"step": "partner_status", "partner_id": partner.partner_id, "status": status}


def _compact(value: object, maximum: int) -> str:
    return " ".join(str(value or "").split())[:maximum].rstrip()


def validate_pitch(pack: dict[str, str]) -> None:
    """Donor partner_copy.validate_partner_content: no medical/guarantee claims, no invented familiarity."""
    text = " ".join(pack.values()).casefold()
    if any(d in text for d in _DENY):
        raise ValueError("partner_copy_forbidden_claim")
    if pack.get("outreach", "").count("!") > 3:
        raise ValueError("partner_copy_too_promotional")
    if any(f in text for f in _FAKE_FAMILIARITY):
        raise ValueError("partner_copy_invented_familiarity")


def ready_post(*, hook: str, target: str, business: str, url: str = "") -> str:
    body = (
        f"{_compact(hook, 180) or 'Практический разбор'}\n\n{_compact(target, 700)}\n\n"
        f"Материал подготовил {business}. Без обещаний чудес: задача — дать понятную пользу, "
        "показать метод и оставить человеку возможность самому решить, подходит ли ему следующий шаг."
    )
    return (body + (f"\n\nУзнать подробности: {url}" if url else ""))[:4900]


def pitch(partner: Partner, *, business: str, offer: str, url: str = "", topic: str = "") -> dict[str, str]:
    """Deterministic, factual partner copy (ported from partner_copy.DeterministicPartnerCopyGenerator)."""
    business, offer = _compact(business, 120), _compact(offer, 360)
    angle = f"полезный материал вокруг «{offer[:180]}»" if offer else "полезный гостевой материал для аудитории"
    topic_line = f"У проекта сейчас заметна тема «{_compact(topic, 180)}». " if topic.strip() else ""
    pack = {
        "subject": f"Материал для аудитории {partner.name}"[:200],
        "outreach": (
            f"Здравствуйте! {topic_line}Я представляю {business}. Предлагаю не рекламную вставку, а {angle}: "
            "мы подготовим текст и возьмём содержательную часть на себя. С вашей стороны — только решение, "
            "подходит ли это аудитории. Если интересно, пришлю готовый вариант поста без обязательств."
        )[:3900],
        "ready_post": ready_post(hook=offer or "Практический разбор", target=offer, business=business, url=url),
        "followup": "Здравствуйте! Один раз напомню о предложении выше. Если тема не подходит — повторно писать не будем.",
        "angle": angle[:480],
        "cta": f"Подробнее: {url}" if url else "Ответьте «интересно» — пришлю готовый материал.",
    }
    validate_pitch(pack)
    return pack


def referral_token(tenant_id: str, partner_id: str) -> str:
    return stable_id("ref", tenant_id, partner_id)[4:16]


def resolve_referral(partners: dict[str, Partner], tenant_id: str, token: str) -> Partner | None:
    """Referral landing (ported from partner_attribution.resolve_partner_referral)."""
    return next((p for p in partners.values() if referral_token(tenant_id, p.partner_id) == token), None)


REFERRAL_EVENTS = ("visit", "lead", "result")


def referral_event(partners: dict[str, Partner], payloads: list[dict[str, Any]], tenant_id: str, token: str,
                   event_type: str, event_key: str | None = None) -> dict[str, Any] | None:
    """Idempotent referral counter fact (donor partner_attribution._record_partner_referral_event).

    Unknown token -> LookupError; an already-recorded (token, type, key) -> None. Stores no personal data.
    """
    if event_type not in REFERRAL_EVENTS:
        raise ValueError("unknown partner referral event")
    tok = str(token or "").strip().removeprefix("ref_")
    partner = resolve_referral(partners, tenant_id, tok)
    if partner is None:
        raise LookupError("partner referral not found")
    key = str(event_key or "")
    if any(p.get("step") == "partner_referral_event" and p.get("partner_id") == partner.partner_id
           and p.get("event_type") == event_type and p.get("event_key", "") == key for p in payloads):
        return None
    return {"step": "partner_referral_event", "partner_id": partner.partner_id, "event_type": event_type,
            "event_key": key}


def record_referral_result(partners: dict[str, Partner], payloads: list[dict[str, Any]], tenant_id: str,
                           token: str, result_key: str) -> dict[str, Any] | None:
    """One confirmed downstream result under a stable non-personal key (donor record_partner_referral_result)."""
    key = str(result_key or "").strip()
    if not key or len(key) > 160:
        raise ValueError("partner result key must be a bounded non-empty value")
    return referral_event(partners, payloads, tenant_id, token, "result", key)


def referral_counts(payloads: list[dict[str, Any]], partner_id: str) -> dict[str, int]:
    out = dict.fromkeys(REFERRAL_EVENTS, 0)
    for p in payloads:
        if p.get("step") == "partner_referral_event" and p.get("partner_id") == partner_id:
            out[p["event_type"]] += 1
    return out


def score(partner: Partner, goal_terms: list[str]) -> Fit:
    goal = {_norm(t) for t in goal_terms if _norm(t)}
    cand = {_norm(t) for t in (*partner.tags, partner.name) if _norm(t)}
    overlap = sum(1 for g in goal if any(g in c or c in g for c in cand)) / max(1, len(goal)) if goal and cand else 0.0
    relevance = min(100.0, 28.0 + overlap * 72.0) if goal else 55.0
    contactability = CONTACTABILITY[partner.basis] if partner.contact else min(CONTACTABILITY[partner.basis], 10.0)
    reasons, penalty = [], 0.0
    if partner.competitor:
        penalty += 65.0
        reasons.append("прямой конкурент")
    if partner.basis not in FIRST_CONTACT_OK:
        penalty += 20.0
        reasons.append("нет основания для первого контакта — только подготовить предложение")
    if partner.followers is not None and partner.followers > 1_000_000:
        penalty += 8.0
        reasons.append("очень большая аудитория — ниже вероятность ответа")
    if overlap > 0.35:
        reasons.append("сильное пересечение аудитории")
    total = relevance * 0.4 + _audience(partner.followers) * 0.2 + contactability * 0.2 + 50.0 * 0.2 - penalty
    return Fit(partner, max(0.0, min(100.0, total)), tuple(reasons))


def rank(partners: dict[str, Partner], goal_terms: list[str], *, limit: int = 10) -> list[Fit]:
    fits = [score(p, goal_terms) for p in partners.values()]
    return sorted(fits, key=lambda f: (-f.total, f.partner.name))[:limit]


def _audience(followers: int | None) -> float:
    if followers is None:
        return 55.0
    if followers <= 0:
        return 20.0
    return max(30.0, min(100.0, 100.0 - abs(math.log10(followers) - math.log10(8_000)) * 28.0))


def _norm(value: object) -> str:
    return " ".join(str(value or "").casefold().replace("ё", "е").split())


__all__ = [
    "STATUSES",
    "Fit",
    "Partner",
    "parse_partner",
    "pitch",
    "rank",
    "referral_token",
    "replay",
    "resolve_referral",
    "score",
    "set_status",
    "statuses",
    "create_quote", "quote_states", "decision", "format_quote",
]


def fallback_terms(activity: str, offerings: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Audience terms from the profile when the goal names none (partner_growth._fallback_terms)."""
    words: list[str] = []
    for src in (activity, *offerings):
        for tok in str(src or "").replace("/", " ").replace(",", " ").split():
            w = tok.strip(".():;!?\"'").casefold()
            if len(w) >= 5 and w not in words:
                words.append(w)
            if len(words) >= 8:
                return tuple(words)
    return tuple(words or ("бизнес",))


def prepare_run(
    discover: Any,
    *,
    goal_terms: list[str],
    activity: str,
    offerings: list[str],
    business: str,
    url: str = "",
    min_fit: float = 55.0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Read-only discovery + local preparation (partner_growth.PartnerGrowthService.run).

    ``discover(terms, limit)`` is the injected provider returning ``parse_partner``-style args;
    ``None`` means not configured. Emits ``partner_added`` + ``partner_pack_prepared`` facts for
    candidates at or above ``min_fit``. Never contacts anyone: sends stay with the executor.
    """
    if not 0 <= float(min_fit) <= 100 or not 1 <= int(limit) <= 500:
        raise ValueError("partner_growth_policy_invalid")
    if discover is None:
        raise ValueError("partner_discovery_not_configured")
    terms = list(goal_terms) or list(fallback_terms(activity, offerings))
    facts: list[dict[str, Any]] = []
    for arg in list(discover(terms, int(limit)))[: int(limit)]:
        added = parse_partner(arg)
        p = replay([added])[added["partner_id"]]
        fit = score(p, terms)
        if fit.total < min_fit:
            continue
        offer = offerings[0] if offerings else ""
        facts += [
            added,
            {
                "step": "partner_pack_prepared",
                "partner_id": p.partner_id,
                "fit": round(fit.total, 1),
                "pack": pitch(p, business=business, offer=offer, url=url),
            },
        ]
    return facts


def start_campaign(name: str, target_count: int, *, today: str) -> dict[str, Any]:
    """Named CAUTIOUS partner campaign, new_customers goal (donor partner_runtime.start_connected_partner_campaign)."""
    title = (" ".join(str(name or "").split()).strip() or f"Партнёрства {today}")[:200]
    target = max(1, min(int(target_count), 500))
    return {"step": "partner_campaign_started", "campaign_id": stable_id("pcamp", title, today), "name": title,
            "target_count": target, "objective": "new_customers", "automation_mode": "cautious"}


def campaigns(payloads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {p["campaign_id"]: p for p in payloads if p.get("step") == "partner_campaign_started"}


def run_campaign(payloads: list[dict[str, Any]], campaign_id: str, discover: Any, **kw: Any) -> list[dict[str, Any]]:
    """(Re)run preparation for an existing campaign (donor rerun_connected_partner_campaign); never contacts."""
    camp = campaigns(payloads).get(campaign_id)
    if camp is None:
        raise ValueError("partner_campaign_not_found")
    known = replay(payloads)
    facts = [f for f in prepare_run(discover, limit=int(camp["target_count"]), **kw)
             if f["step"] != "partner_added" or f["partner_id"] not in known]
    return [{**f, "campaign_id": campaign_id} for f in facts]


_CURRENCIES = frozenset({"RUB", "USD", "EUR"})
_SCOPE_LIMIT = 500
_REFERENCE = re.compile(r"^[a-zA-Z0-9:_-]{3,128}$")


def create_quote(partner_id: str, amount_minor: str, currency: str, scope: str) -> dict[str, Any]:
    if not _REFERENCE.fullmatch(str(partner_id)):
        raise ValueError("partner_id_invalid")
    # Strict decimal integer; floats/negative amounts cannot authorize spending.
    if not isinstance(amount_minor, str) or not re.fullmatch(r"[0-9]{1,12}", amount_minor):
        raise ValueError("partner_amount_minor_invalid")
    amount = int(amount_minor)
    if not 0 < amount <= 10_000_000_000:
        raise ValueError("partner_amount_out_of_range")
    currency = currency.strip().upper()
    if currency not in _CURRENCIES:
        raise ValueError("partner_currency_unsupported")
    scope = " ".join(scope.split())
    if not scope or len(scope) > _SCOPE_LIMIT or any(ord(ch) < 32 for ch in scope):
        raise ValueError("partner_scope_invalid")
    canonical = json.dumps([partner_id, amount, currency, scope], ensure_ascii=False, separators=(",", ":"))
    quote_id = "pq_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return {
        "step": "partner_quote_drafted", "partner_id": partner_id, "quote_id": quote_id,
        "amount_minor": amount, "currency": currency, "scope": scope,
        "status": "pending_owner_approval",
    }


def quote_states(payloads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for fact in payloads:
        step = fact.get("step")
        quote_id = str(fact.get("quote_id") or "")
        if step == "partner_quote_drafted" and quote_id:
            states.setdefault(quote_id, dict(fact))
        elif (step in {"partner_quote_approved", "partner_quote_rejected"}
              and quote_id in states and states[quote_id]["status"] == "pending_owner_approval"):
            states[quote_id]["status"] = "owner_approved" if step.endswith("approved") else "rejected"
    return states


def decision(payloads: list[dict[str, Any]], quote_id: str, *, approve: bool) -> dict[str, Any] | None:
    states = quote_states(payloads)
    quote = states.get(quote_id)
    if quote is None:
        raise LookupError("partner_quote_not_found")
    if quote["status"] != "pending_owner_approval":
        return None if quote["status"] == ("owner_approved" if approve else "rejected") else _conflict()
    return {
        "step": "partner_quote_approved" if approve else "partner_quote_rejected",
        "quote_id": quote_id, "partner_id": quote["partner_id"],
        "approval_scope": "internal_only_no_send_no_payment" if approve else "none",
    }


def _conflict() -> None:
    raise ValueError("partner_quote_already_decided")


def format_quote(quote: dict[str, Any]) -> str:
    amount = int(quote["amount_minor"])
    return (f"{quote['quote_id']} · {amount // 100},{amount % 100:02d} {quote['currency']}"
            f" · {quote['status']}\nУсловия: {escape(str(quote['scope']), quote=False)}")


# A private Telegram invitation is the only supported partner messaging address.
# The clear token is shown to the owner once; only its digest enters the event log.
def invitation(partner_id: str, token: str, expires_at: int) -> dict[str, Any]:
    if not _REFERENCE.fullmatch(partner_id) or not re.fullmatch(r"[A-Za-z0-9_-]{24,128}", token):
        raise ValueError("partner_invitation_invalid")
    if not isinstance(expires_at, int) or isinstance(expires_at, bool) or expires_at <= 0:
        raise ValueError("partner_invitation_expiry_invalid")
    return {"step": "partner_invited", "partner_id": partner_id,
            "token_hash": hashlib.sha256(token.encode("ascii")).hexdigest(),
            "expires_at": expires_at}


def bound_contacts(payloads: list[dict[str, Any]]) -> dict[str, str]:
    """Only bindings acknowledged through the canonical Telegram inbound flow."""
    contacts: dict[str, str] = {}
    for fact in payloads:
        if fact.get("step") == "partner_joined" and fact.get("channel") == "telegram":
            partner_id = str(fact.get("partner_id") or "")
            user_id = str(fact.get("telegram_user_id") or "")
            if partner_id and user_id.isascii() and user_id.isdecimal() and int(user_id) > 0:
                contacts[partner_id] = user_id
        elif fact.get("step") == "partner_unsubscribed":
            partner_id = str(fact.get("partner_id") or "")
            if contacts.get(partner_id) == str(fact.get("telegram_user_id") or ""):
                del contacts[partner_id]
    return contacts


def claim_invitation(payloads: list[dict[str, Any]], token: str, user_id: str, *, now: int) -> dict[str, Any] | None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,128}", token) or not user_id.isascii() or not user_id.isdecimal() or int(user_id) <= 0:
        raise ValueError("partner_join_invalid")
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    invitations = {p["token_hash"]: p for p in payloads if p.get("step") == "partner_invited"}
    offer = invitations.get(digest)
    if offer is None or int(offer["expires_at"]) < now:
        raise ValueError("partner_invitation_missing_or_expired")
    partner_id = str(offer["partner_id"])
    prior = [p for p in payloads if p.get("step") == "partner_joined" and p.get("token_hash") == digest]
    if prior:
        if str(prior[0]["telegram_user_id"]) == user_id:
            if bound_contacts(payloads).get(partner_id) == user_id:
                return None
            raise ValueError("partner_invitation_no_longer_active")
        raise ValueError("partner_invitation_already_claimed")
    if partner_id not in replay(payloads):
        raise ValueError("partner_not_found")
    contacts = bound_contacts(payloads)
    if any(pid != partner_id and uid == user_id for pid, uid in contacts.items()):
        raise ValueError("partner_telegram_identity_already_bound")
    contact = contacts.get(partner_id)
    if contact and contact != user_id:
        raise ValueError("partner_already_bound")
    return {"step": "partner_joined", "partner_id": partner_id, "channel": "telegram",
            "telegram_user_id": user_id, "token_hash": digest}


def conversation(payloads: list[dict[str, Any]], partner_id: str) -> list[dict[str, Any]]:
    return [p for p in payloads if p.get("partner_id") == partner_id and p.get("step") in
            {"partner_message_in", "partner_message_out"}]


def inbound_message(payloads: list[dict[str, Any]], user_id: str, text: str, message_key: str) -> dict[str, Any] | None:
    contact = next((partner for partner, uid in bound_contacts(payloads).items() if uid == user_id), None)
    if not contact:
        raise PermissionError("partner_not_verified")
    content = text.strip()
    if not content or len(content) > 2000 or any(ord(ch) < 32 and ch not in "\n\t" for ch in content):
        raise ValueError("partner_message_invalid")
    if not message_key or len(message_key) > 160:
        raise ValueError("partner_message_key_invalid")
    if any(p.get("step") == "partner_message_in" and p.get("message_key") == message_key for p in payloads):
        return None
    return {"step": "partner_message_in", "partner_id": contact, "text": content,
            "message_key": message_key, "channel": "telegram"}


def outbound_message(payloads: list[dict[str, Any]], partner_id: str, text: str, message_key: str) -> dict[str, Any]:
    if partner_id not in replay(payloads) or partner_id not in bound_contacts(payloads):
        raise ValueError("partner_not_bound")
    content = text.strip()
    if not content or len(content) > 2000 or any(ord(ch) < 32 and ch not in "\n\t" for ch in content):
        raise ValueError("partner_message_invalid")
    if not message_key or len(message_key) > 160:
        raise ValueError("partner_message_key_invalid")
    return {"step": "partner_message_out", "partner_id": partner_id, "text": content,
            "message_key": message_key, "channel": "telegram"}


def unsubscribe(payloads: list[dict[str, Any]], user_id: str) -> dict[str, Any] | None:
    partner_id = next((pid for pid, uid in bound_contacts(payloads).items() if uid == user_id), "")
    if not partner_id:
        return None
    return {"step": "partner_unsubscribed", "partner_id": partner_id,
            "telegram_user_id": user_id, "channel": "telegram"}

PARTNER_BUDGET_KEY_PREFIX = "partner_budget_limit_minor."


def budget_check(payloads: list[dict[str, Any]], settings: dict[str, str],
                 quote_id: str) -> dict[str, Any]:
    """Fail-closed tenant budget policy for *internal* quote approval.

    This is not a payment authorization or a durable funds reservation.
    Quote IDs are content-addressed immutable revisions; approved quotes count
    against the configured ceiling until a canonical budget owner supersedes it.
    """
    quote = quote_states(payloads).get(quote_id)
    if quote is None:
        raise LookupError("partner_quote_not_found")
    currency = str(quote["currency"]).upper()
    raw = settings.get(PARTNER_BUDGET_KEY_PREFIX + currency.lower())
    if raw is None:
        raise PermissionError("partner_budget_not_configured")
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]{1,12}", raw):
        raise ValueError("partner_budget_invalid")
    limit = int(raw)
    if not 0 < limit <= 10_000_000_000:
        raise ValueError("partner_budget_invalid")
    states = quote_states(payloads)
    used = sum(int(q["amount_minor"]) for q in states.values()
               if q["status"] == "owner_approved" and q["currency"] == currency)
    amount = int(quote["amount_minor"])
    if used + amount > limit:
        raise PermissionError("partner_budget_exceeded")
    return {
        "budget_limit_minor": limit,
        "budget_used_minor": used,
        "budget_checked_currency": currency,
        "budget_policy": "internal_quote_ceiling_not_funds_reservation",
    }


def partner_card(known, op, arg, tenant_id, facts):
    from application.business_flows import partners as pt

    ordered = sorted(known.values(), key=lambda p: p.name)
    head, _, rest = arg.partition(" ")
    partner = known.get(head) if head in known else (ordered[int(head) - 1] if head.isdigit() and 0 < int(head) <= len(ordered) else None)
    change = None
    try:
        if partner is None:
            raise ValueError("partner_not_found: номер партнёра по алфавиту")
        if op == "status":
            change = pt.set_status(partner, pt.statuses(facts).get(partner.partner_id, "new"), rest.strip())
            text = f"🤝 {partner.name}: {pt.STATUSES[change['status']]}"
        elif op == "pitch":
            business, _, offer = rest.partition("|")
            pack = pt.pitch(partner, business=business.strip() or "наш проект", offer=offer.strip())
            text = f"✉️ {pack['subject']}\n\n{pack['outreach']}\n\n{pack['cta']}\n\nНапоминание: {pack['followup']}\n(Отправляете вы сами.)"
        else:
            text = f"🔗 Реферальный код партнёра {partner.name}: ref_{pt.referral_token(tenant_id, partner.partner_id)}"
    except ValueError as exc:
        return f"🤝 Не получилось: {exc}", None
    return text, change



