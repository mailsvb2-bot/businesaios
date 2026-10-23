"""Ad publication as governed proposals (port of clientplatform ad publication/spend consent).

Nothing here spends money or calls a provider. Flow:
``/ad_draft`` stores a draft; ``/ad_consent`` turns it into an owner approval with an
exact weekly cap (existing ``business_admin`` approvals: /approve, /reject, /revoke);
``/ad_publish`` is evaluated against the approval AND the connector truth
(``production_ready``/``requires_human_approval``) and, while the connector is not
production-ready, only records that publication is blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.business_flows import admin as ad
from application.business_flows.projection import stable_id

TITLE_MAX, TEXT_MAX = 56, 81  # Yandex Direct text-ad limits


@dataclass
class AdDraft:
    draft_id: str
    title: str
    text: str
    url: str
    status: str = "draft"
    approval_id: str = ""
    weekly_cap_minor: int = 0
    currency: str = "RUB"


def replay(payloads: list[dict[str, Any]]) -> dict[str, AdDraft]:
    out: dict[str, AdDraft] = {}
    for p in payloads:
        step, did = p.get("step"), p.get("draft_id")
        if step == "ad_drafted" and did not in out:
            out[did] = AdDraft(did, p["title"], p["text"], p["url"])
        elif step == "approval_requested" and did in out:
            d = out[did]
            d.status, d.approval_id = "awaiting_approval", p["approval_id"]
            d.weekly_cap_minor, d.currency = int(p["weekly_cap_minor"]), p["currency"]
        elif step == "ad_publish_blocked" and did in out:
            out[did].status = "blocked"
        elif step == "ad_copy_edited" and did in out:
            out[did].title, out[did].text = p["title"], p["text"]
    return out


def draft(arg: str) -> dict[str, Any]:
    parts = [x.strip() for x in str(arg or "").split("|")]
    if len(parts) != 3 or not all(parts):
        raise ValueError("формат: /ad_draft Заголовок | Текст | https://ссылка")
    title, text, url = parts
    if len(title) > TITLE_MAX or len(text) > TEXT_MAX:
        raise ValueError(f"заголовок до {TITLE_MAX}, текст до {TEXT_MAX} символов")
    if not url.startswith("https://") or " " in url:
        raise ValueError("ссылка должна начинаться с https://")
    return {
        "step": "ad_drafted",
        "draft_id": stable_id("addraft", title, text, url),
        "title": title,
        "text": text,
        "url": url,
    }


def _norm(value: object, *, limit: int, word: int, what: str) -> str:
    """Donor ad_publication_customization._normalize_title/_normalize_text (Yandex Direct limits)."""
    v = " ".join(str(value or "").split()).strip()
    if not v or len(v) > limit:
        raise ValueError(f"{what}: от 1 до {limit} символов")
    if any(len(w) > word for w in v.split()):
        raise ValueError(f"{what}: слово длиннее {word} символов")
    return v


def normalize_title(value: object) -> str:
    return _norm(value, limit=TITLE_MAX, word=22, what="заголовок")


def normalize_text(value: object) -> str:
    return _norm(value, limit=TEXT_MAX, word=23, what="текст")


EDITABLE = {"draft", "blocked"}  # donor: draft/failed/submitted (provider DRAFT, before spend consent)


def edit_copy(drafts: dict[str, AdDraft], arg: str) -> dict[str, Any] | None:
    """``N | Заголовок | Текст`` -> ``ad_copy_edited`` fact; only before consent; None if unchanged."""
    parts = [x.strip() for x in str(arg or "").split("|")]
    if len(parts) != 3:
        raise ValueError("формат: /ad_edit N | Заголовок | Текст")
    d = by_ref(drafts, parts[0])
    if d.status not in EDITABLE:
        raise ValueError("черновик уже нельзя редактировать")
    title, text = normalize_title(parts[1]), normalize_text(parts[2])
    if (title, text) == (d.title, d.text):
        return None
    return {"step": "ad_copy_edited", "draft_id": d.draft_id, "title": title, "text": text}


def by_ref(drafts: dict[str, AdDraft], ref: str) -> AdDraft:
    items = list(drafts.values())
    ref = str(ref or "").strip()
    if ref.isdigit() and 0 < int(ref) <= len(items):
        return items[int(ref) - 1]
    if ref in drafts:
        return drafts[ref]
    raise ValueError("черновик не найден, см. /ads")


def approval_title(title: str, amount_minor: int, currency: str) -> str:
    return f"Реклама «{title}», кап {ad.money(amount_minor, currency)}/нед"[:200]


def consent(drafts: dict[str, AdDraft], arg: str, *, min_weekly_minor: int) -> dict[str, Any]:
    """``N | 5000 RUB`` -> one existing ``approval_requested`` fact bound to the draft and exact cap."""
    ref, _, cap = (x.strip() for x in str(arg or "").partition("|"))
    d = by_ref(drafts, ref)
    if d.status != "draft":
        raise ValueError("согласие уже запрошено")
    amount, cur = ad.parse_money(cap)
    if amount < min_weekly_minor:
        raise ValueError(f"недельный кап ниже минимума {ad.money(min_weekly_minor, cur)}")
    appr = ad.request_approval(approval_title(d.title, amount, cur), amount, cur, source_ref=d.draft_id)
    return {**appr, "draft_id": d.draft_id, "weekly_cap_minor": amount}


def publish_decision(
    d: AdDraft, approvals: dict[str, ad.Approval], *, production_ready: bool
) -> tuple[str, dict[str, Any] | None]:
    """Never returns a 'go' while production_ready is False; returns (message, fact)."""
    ap = approvals.get(d.approval_id)
    if ap is None:
        return "Сначала запросите согласие: /ad_consent N | кап", None
    if ap.status != "approved":
        return f"Согласие не одобрено (статус: {ap.status}). /approvals", None
    from application.business_flows.automation_policy import authorize

    try:  # executor-side binding: the approval must name exactly this draft title and cap
        authorize(
            approvals,
            d.approval_id,
            title=approval_title(d.title, d.weekly_cap_minor, d.currency),
            amount_minor=d.weekly_cap_minor,
        )
    except PermissionError as exc:
        return f"🔒 Публикация отклонена: {exc}", None
    if not production_ready:
        return (
            "🔒 Одобрено, но публикация заблокирована: коннектор Яндекс Директа не готов к продакшену "
            "(production_ready=False). Деньги не тратятся.",
            {"step": "ad_publish_blocked", "draft_id": d.draft_id, "reason": "connector_not_production_ready"}
            if d.status != "blocked"
            else None,
        )
    raise PermissionError("live_ad_publication_not_wired")  # deliberate: live path needs a reviewed gateway binding


STATUS = {"draft": "черновик", "awaiting_approval": "ждёт согласия", "blocked": "одобрено, публикация заблокирована"}


def list_text(drafts: dict[str, AdDraft], approvals: dict[str, ad.Approval]) -> str:
    rows = []
    for n, d in enumerate(drafts.values(), 1):
        st = STATUS[d.status]
        if d.approval_id in approvals and d.status == "awaiting_approval":
            st = {"approved": "одобрено", "rejected": "отклонено", "revoked": "отозвано"}.get(
                approvals[d.approval_id].status, st
            )
        cap = f" · кап {ad.money(d.weekly_cap_minor, d.currency)}/нед" if d.weekly_cap_minor else ""
        rows.append(f"{n}. {d.title} — {st}{cap}")
    return "📣 Реклама (только предложения, без расходов)\n" + ("\n".join(rows) or "Черновиков нет. /ad_draft")
