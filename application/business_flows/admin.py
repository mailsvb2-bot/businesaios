"""Owner admin operations: settings, autopilot, offering prices, manual payments/refunds, approvals.

Ported from clientplatform ``admin_ops`` onto the event-sourced flow pattern: every
mutation is one ``business_admin@v1`` fact (the delivered receipt), replay is the audit
trail. Money is integer minor units; a payment's external reference is idempotent, a
refund never exceeds what remains. Nothing here moves money: payments are owner-recorded
evidence (cash/transfer), not the provider Payment lifecycle owned by core.payments.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from application.business_flows.projection import stable_id

CANON_BUSINESS_ADMIN_FLOW = True
CURRENCIES = {"RUB": "₽", "USD": "$", "EUR": "€", "KZT": "₸"}
MAX_MINOR = 10**11
_KEY = re.compile(r"^[a-z][a-z0-9_.]{0,119}$")
APPROVAL_NEXT = {
    "approve": ("pending", "approved"),
    "reject": ("pending", "rejected"),
    "revoke": ("approved", "revoked"),
}


@dataclass
class ManualPaymentRecord:
    payment_id: str
    offering: str
    amount_minor: int
    currency: str
    reference: str
    refunded_minor: int = 0
    refunds: list[str] = field(default_factory=list)
    customer_id: str = ""

    @property
    def remaining_minor(self) -> int:
        return self.amount_minor - self.refunded_minor


@dataclass
class Approval:
    approval_id: str
    title: str
    amount_minor: int
    currency: str
    status: str = "pending"


@dataclass
class State:
    settings: dict[str, str] = field(default_factory=dict)
    prices: dict[str, tuple[int, str]] = field(default_factory=dict)
    payments: dict[str, ManualPaymentRecord] = field(default_factory=dict)
    approvals: dict[str, Approval] = field(default_factory=dict)
    archived_customers: set[str] = field(default_factory=set)

    @property
    def autopilot(self) -> bool:
        return self.settings.get("autopilot_enabled") == "1"


def money(amount_minor: int, currency: str) -> str:
    whole, frac = divmod(int(amount_minor), 100)
    return f"{whole},{frac:02d} {CURRENCIES.get(currency, currency)}"


def parse_money(text: str) -> tuple[int, str]:
    parts = str(text or "").strip().split()
    if not parts:
        raise ValueError("amount_missing")
    cur = (parts[1] if len(parts) > 1 else "RUB").upper()
    if cur not in CURRENCIES:
        raise ValueError("currency_unsupported")
    m = re.fullmatch(r"(\d{1,12})(?:[.,](\d{1,2}))?", parts[0])
    if not m:
        raise ValueError("amount_invalid")
    minor = int(m.group(1)) * 100 + int((m.group(2) or "0").ljust(2, "0"))
    if not 0 < minor <= MAX_MINOR:
        raise ValueError("amount_out_of_range")
    return minor, cur


def _fields(arg: str, n: int, usage: str) -> list[str]:
    parts = [p.strip() for p in str(arg or "").split("|")]
    if len(parts) < n or not all(parts[:n]):
        raise ValueError(usage)
    return parts


def replay(payloads: list[dict[str, Any]]) -> State:
    st = State()
    for p in payloads:
        step = p.get("step")
        if step == "setting_set":
            st.settings[str(p["key"])] = str(p["value"])
        elif step == "price_set":
            st.prices[str(p["offering"])] = (int(p["amount_minor"]), str(p["currency"]))
        elif step == "payment_recorded" and p["payment_id"] not in st.payments:
            st.payments[p["payment_id"]] = ManualPaymentRecord(
                p["payment_id"],
                p["offering"],
                int(p["amount_minor"]),
                p["currency"],
                p["reference"],
                customer_id=str(p.get("customer_id") or ""),
            )
        elif step == "payment_refunded" and p["payment_id"] in st.payments:
            pay = st.payments[p["payment_id"]]
            if p["refund_id"] not in pay.refunds:
                pay.refunds.append(p["refund_id"])
                pay.refunded_minor += int(p["amount_minor"])
        elif step == "approval_requested" and p["approval_id"] not in st.approvals:
            st.approvals[p["approval_id"]] = Approval(
                p["approval_id"], p["title"], int(p["amount_minor"]), p["currency"]
            )
        elif step == "customer_archived":
            st.archived_customers.add(str(p["customer_id"]))
        elif step == "customer_restored":
            st.archived_customers.discard(str(p["customer_id"]))
        elif step == "approval_decided" and p["approval_id"] in st.approvals:
            st.approvals[p["approval_id"]].status = str(p["status"])
    return st


def set_setting(st: State, arg: str) -> dict[str, Any]:
    key, _, value = str(arg or "").partition("=")
    key, value = key.strip().casefold(), value.strip()
    if not _KEY.match(key) or not value or len(value) > 1000:
        raise ValueError("setting_format: /setting ключ = значение")
    return {"step": "setting_set", "key": key, "value": value}


def archive_customer(st: State, arg: str, known: set[str]) -> dict[str, Any] | None:
    """Donor archive_customer: ``ID`` hides a known customer from the cockpit list, ``ID off`` restores.

    History and bookings stay intact (facts are never deleted); idempotent: None when already in that state.
    """
    parts = str(arg or "").split()
    if not parts or parts[0] not in known:
        raise ValueError("customer_unknown: /customer_archive ID [off]")
    cid, restore = parts[0], len(parts) > 1 and parts[1].casefold() == "off"
    if restore:
        return {"step": "customer_restored", "customer_id": cid} if cid in st.archived_customers else None
    return None if cid in st.archived_customers else {"step": "customer_archived", "customer_id": cid}


def set_autopilot(st: State, arg: str) -> dict[str, Any] | None:
    """on|off|toggle (default toggle); idempotent: None when already in the desired state."""
    word = str(arg or "toggle").strip().casefold()
    want = {"on": True, "off": False, "toggle": not st.autopilot}.get(word)
    if want is None:
        raise ValueError("autopilot_format: /autopilot on|off")
    if want == st.autopilot:
        return None
    return {"step": "setting_set", "key": "autopilot_enabled", "value": "1" if want else "0"}


def set_price(st: State, arg: str) -> dict[str, Any]:
    offering, amount = _fields(arg, 2, "price_format: /price Предложение | 1500 RUB")[:2]
    minor, cur = parse_money(amount)
    return {"step": "price_set", "offering": offering[:120], "amount_minor": minor, "currency": cur}


def record_payment(st: State, arg: str) -> tuple[dict[str, Any] | None, ManualPaymentRecord | None]:
    """``Предложение | сумма [валюта] | внешняя ссылка [| id клиента]``; same reference replays, never doubles."""
    p = _fields(arg, 3, "payment_format: /pay Предложение | 1500 RUB | номер платежа")
    payment_id = stable_id("pay", p[2].casefold())
    if payment_id in st.payments:
        prior = st.payments[payment_id]
        if prior.offering != p[0][:120] or (prior.amount_minor, prior.currency) != parse_money(p[1]):
            raise ValueError("payment_reference_reused_with_different_terms")
        return None, prior
    if p[0][:120] not in st.prices and st.prices:
        raise ValueError("offering_unknown")
    minor, cur = parse_money(p[1])
    change = {
        "step": "payment_recorded",
        "payment_id": payment_id,
        "offering": p[0][:120],
        "amount_minor": minor,
        "currency": cur,
        "reference": p[2][:120],
    }
    customer = p[3].strip()[:80] if len(p) > 3 else ""
    if customer:  # donor _payment_new_result links the payment to a customer
        change["customer_id"] = customer
    return change, None


def refund_payment(st: State, arg: str) -> dict[str, Any] | None:
    """``ссылка платежа | сумма | ссылка возврата`` (сумма optional = остаток); idempotent by refund ref."""
    p = [x.strip() for x in str(arg or "").split("|")]
    if not p[0]:
        raise ValueError("refund_format: /refund номер платежа | сумма | номер возврата")
    pay = st.payments.get(stable_id("pay", p[0].casefold()))
    if pay is None:
        raise ValueError("payment_not_found")
    refund_id = stable_id("refund", pay.payment_id, (p[2] if len(p) > 2 and p[2] else p[0]).casefold())
    if refund_id in pay.refunds:
        return None
    minor = pay.remaining_minor if len(p) < 2 or not p[1] else parse_money(f"{p[1]} {pay.currency}")[0]
    if minor <= 0 or minor > pay.remaining_minor:
        raise ValueError("refund_exceeds_remaining")
    return {"step": "payment_refunded", "payment_id": pay.payment_id, "refund_id": refund_id, "amount_minor": minor}


def request_approval(title: str, amount_minor: int, currency: str, *, source_ref: str) -> dict[str, Any]:
    """Producer side for automation proposals that need the owner's yes before any effect."""
    return {
        "step": "approval_requested",
        "approval_id": stable_id("appr", source_ref),
        "title": str(title)[:200],
        "amount_minor": int(amount_minor),
        "currency": currency,
    }


def decide_approval(st: State, verb: str, arg: str) -> dict[str, Any]:
    src, dst = APPROVAL_NEXT[verb]
    ap = _approval_by_ref(st, arg)
    if ap.status != src:
        raise ValueError(f"approval_not_{src}")
    return {"step": "approval_decided", "approval_id": ap.approval_id, "status": dst}


def _approval_by_ref(st: State, arg: str) -> Approval:
    items = list(st.approvals.values())
    ref = str(arg or "").strip()
    if ref.isdigit() and 0 < int(ref) <= len(items):
        return items[int(ref) - 1]
    if ref in st.approvals:
        return st.approvals[ref]
    raise ValueError("approval_not_found")


def format_approval(n: int, ap: Approval) -> str:
    status = {"pending": "ждёт решения", "approved": "одобрено", "rejected": "отклонено", "revoked": "отозвано"}
    return f"{n}. {ap.title} — {money(ap.amount_minor, ap.currency)} · {status[ap.status]}"


def payment_summary(st: State) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for pay in st.payments.values():
        row = out.setdefault(pay.currency, {"count": 0, "gross_minor": 0, "refunded_minor": 0, "net_minor": 0})
        row["count"] += 1
        row["gross_minor"] += pay.amount_minor
        row["refunded_minor"] += pay.refunded_minor
        row["net_minor"] += pay.remaining_minor
    return out


def render_summary(st: State) -> str:
    lines = ["💳 Платежи (записаны владельцем)"]
    for cur, row in sorted(payment_summary(st).items()):
        lines.append(
            f"{cur}: {row['count']} шт., получено {money(row['gross_minor'], cur)}, "
            f"возвраты {money(row['refunded_minor'], cur)}, итого {money(row['net_minor'], cur)}"
        )
    if len(lines) == 1:
        lines.append("Пока нет записанных платежей.")
    pending = sum(1 for a in st.approvals.values() if a.status == "pending")
    lines.append(f"Автопилот: {'включён' if st.autopilot else 'выключен'} · ждут решения: {pending}")
    return "\n".join(lines)


def audit_lines(payloads: list[dict[str, Any]], *, limit: int = 20) -> list[str]:
    """Donor recent_audit_events: newest owner-admin facts first (replay is the audit trail)."""
    n = max(1, min(int(limit), 100))
    rows = []
    for p in list(payloads)[::-1][:n]:
        subject = p.get("key") or p.get("offering") or p.get("reference") or p.get("title") or p.get("status") or ""
        rows.append(f"• {p.get('step', '?')} {str(subject)[:60]}".rstrip())
    return rows or ["• Записей пока нет."]


# --- AI-commerce usage/limits (port of clientplatform.application.ai_commerce) ---------------------------
# Usage is read from canonical projections (team roles, bookings customers); no private commerce ledger.
STAFF_SEAT_SKU, ACTIVE_CUSTOMER_SKU = "staff_seat", "active_customer"
DEFAULT_ALLOWANCES = {STAFF_SEAT_SKU: 5, ACTIVE_CUSTOMER_SKU: 500}  # donor 'base' plan
SKU_LABELS = {STAFF_SEAT_SKU: "сотрудники", ACTIVE_CUSTOMER_SKU: "клиенты"}


def allowances(st: State) -> dict[str, int]:
    """Plan allowances: owner/operator settings ``plan.staff_seat`` / ``plan.active_customer`` or donor base."""
    out = {}
    for sku, default in DEFAULT_ALLOWANCES.items():
        raw = st.settings.get(f"plan.{sku}", "")
        out[sku] = int(raw) if raw.isdigit() else default
    return out


def commerce_proposal(
    *, operation_id: str, tenant_id: str, sku: str, requested_units: int, used: int, allowance: int
) -> dict[str, Any]:
    """Donor prepare_ai_commerce_proposal/build_proposal: included vs upgrade, deterministic proposal id."""
    if sku not in DEFAULT_ALLOWANCES:
        raise ValueError("sku: " + ", ".join(DEFAULT_ALLOWANCES))
    if not 1 <= int(requested_units) <= 100_000 or used < 0 or allowance < 0:
        raise ValueError("количество: целое от 1")
    projected = used + int(requested_units)
    upgrade = projected > allowance
    return {
        "proposal_id": stable_id("aic", operation_id, tenant_id, sku, requested_units),
        "operation_id": operation_id,
        "sku": sku,
        "kind": "upgrade" if upgrade else "included",
        "reason": "canonical allowance exceeded" if upgrade else "covered by canonical allowance",
        "used": used,
        "allowance": allowance,
        "requested_units": int(requested_units),
        "projected_total": projected,
    }


def commerce_usage(event_store, tenant_id: str, user_id: str, archived: set[str]) -> dict[str, int]:
    """Live usage from canonical projections: team roles (+ current owner) and distinct booking customers."""
    from application.business_flows.projection import flow_payloads
    from core.admin.roles_read_model import team_roles_snapshot

    staff = set(team_roles_snapshot(event_store, tenant_id=tenant_id)) | {user_id}
    seen = {
        str(p.get("customer_id") or "")
        for p in flow_payloads(event_store, tenant_id=tenant_id, event_type="bookings@v1")
    }
    return {STAFF_SEAT_SKU: len(staff - {""}), ACTIVE_CUSTOMER_SKU: len(seen - {""} - set(archived))}


def commerce_overview(st: State, *, tenant_id: str, usage: dict[str, int]) -> dict[str, dict[str, Any]]:
    """Donor get_commerce_overview: one-unit preview per SKU against the plan allowance."""
    lim = allowances(st)
    return {
        sku: commerce_proposal(
            operation_id=f"tariff-preview:{sku}:{usage.get(sku, 0)}:{lim[sku]}",
            tenant_id=tenant_id,
            sku=sku,
            requested_units=1,
            used=int(usage.get(sku, 0)),
            allowance=lim[sku],
        )
        for sku in DEFAULT_ALLOWANCES
    }


def expansion_recommended(overview: dict[str, dict[str, Any]]) -> bool:
    return any(p["kind"] == "upgrade" for p in overview.values())


def commerce_text(overview: dict[str, dict[str, Any]]) -> str:
    rows = [
        f"• {SKU_LABELS[sku]}: {p['used']}/{p['allowance']}"
        + (" — нужен больший тариф" if p["kind"] == "upgrade" else "")
        for sku, p in overview.items()
    ]
    tail = "\nРекомендуем расширение: /commerce_expand" if expansion_recommended(overview) else ""
    return "📊 Тариф и лимиты\n" + "\n".join(rows) + tail


def expansion_request(overview: dict[str, dict[str, Any]], *, tenant_id: str, known: set[str]) -> dict[str, Any] | None:
    """Donor request_subscription_expansion: idempotent billing support-case fact (operator handles it)."""
    reasons = [f"{SKU_LABELS[s]} {p['used']}/{p['allowance']}" for s, p in overview.items() if p["kind"] == "upgrade"]
    reasons = reasons or ["владелец запросил информацию о расширении до исчерпания текущих лимитов"]
    fp = ":".join(f"{p['used']}:{p['allowance']}" for p in overview.values())
    key = f"ai-commerce-expansion:{tenant_id}:{fp}"
    if key in known:
        return None
    summary = "Запрос владельца на расширение тарифа: " + "; ".join(reasons)
    return {"step": "support_case_requested", "category": "billing", "idempotency_key": key, "title": summary}


def requested_cases(payloads: list[dict[str, Any]]) -> set[str]:
    return {str(p["idempotency_key"]) for p in payloads if p.get("step") == "support_case_requested"}


# --- business retirement: two-step owner confirmation, archive without data loss (donor archive_business) ---
# A retired business is only marked archived: payments, results, audit and every other fact stay intact and the
# business can be restored. Off by default (BAI_BUSINESS_RETIRE_ENABLED): with the flag off a confirmed request is
# recorded as a dry run and nothing is archived.
RETIRE_ENV = "BAI_BUSINESS_RETIRE_ENABLED"
RETIRE_TTL_SECONDS = 300


def retire_enabled(env: Mapping[str, str] | None = None) -> bool:
    return str((env if env is not None else os.environ).get(RETIRE_ENV) or "").strip().lower() in {"1", "true", "yes", "on"}


def _code_hash(code: str) -> str:
    return hashlib.sha256(str(code).strip().upper().encode()).hexdigest()


def retire_status(payloads: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    """active | pending (code issued, not expired) | archived. Replay of ``business_retire_*``/``business_archived``."""
    out: dict[str, Any] = {"status": "active", "name": "", "code_hash": "", "expires_at": ""}
    for p in payloads:
        step = p.get("step")
        if step == "business_retire_requested" and out["status"] == "active":
            out.update(status="pending", name=str(p.get("business_name") or ""), code_hash=str(p["code_hash"]),
                       expires_at=str(p["expires_at"]))
        elif step == "business_retire_cancelled" and out["status"] == "pending":
            out.update(status="active", code_hash="", expires_at="")
        elif step == "business_archived":
            out.update(status="archived", name=str(p.get("business_name") or out["name"]), code_hash="", expires_at="")
        elif step == "business_restored" and out["status"] == "archived":
            out.update(status="active", code_hash="", expires_at="")
    if out["status"] == "pending" and now is not None and now >= datetime.fromisoformat(out["expires_at"]):
        out.update(status="active", code_hash="", expires_at="")
    return out


def is_archived(payloads: list[dict[str, Any]]) -> bool:
    return retire_status(payloads)["status"] == "archived"


def retire_request(payloads: list[dict[str, Any]], *, name: str, nonce: str, now: datetime) -> tuple[dict[str, Any], str]:
    """Step 1: issue a short-lived confirmation code (only its hash is stored). Nothing is archived yet."""
    if retire_status(payloads, now)["status"] == "archived":
        raise ValueError("бизнес уже в архиве")
    code = str(nonce).strip().upper()
    if not re.fullmatch(r"[0-9A-F]{8}", code):
        raise ValueError("invalid retire nonce")
    fact = {"step": "business_retire_requested", "business_name": str(name).strip()[:120], "code_hash": _code_hash(code),
            "expires_at": (now + timedelta(seconds=RETIRE_TTL_SECONDS)).isoformat(), "at": now.isoformat()}
    return fact, code


def retire_confirm(payloads: list[dict[str, Any]], *, code: str, now: datetime, env: Mapping[str, str] | None = None) -> dict[str, Any] | None:
    """Step 2: the exact code from step 1 inside its TTL. Flag off -> dry-run fact. Already archived -> None (idempotent)."""
    cur = retire_status(payloads, now)
    if cur["status"] == "archived":
        return None
    if cur["status"] != "pending":
        raise ValueError("нет активного запроса на удаление или код истёк: начните заново /business_retire")
    if not hmac.compare_digest(cur["code_hash"], _code_hash(code)):
        raise ValueError("неверный код подтверждения")
    if not retire_enabled(env):
        return {"step": "business_retire_dry_run", "business_name": cur["name"], "flag": RETIRE_ENV, "at": now.isoformat()}
    return {"step": "business_archived", "business_name": cur["name"], "data_preserved": True,
            "idempotency_key": "business_archived:" + cur["code_hash"][:16], "at": now.isoformat()}


def retire_cancel(payloads: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    if retire_status(payloads, now)["status"] != "pending":
        return None
    return {"step": "business_retire_cancelled", "at": now.isoformat()}


def business_restore(payloads: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    if retire_status(payloads)["status"] != "archived":
        return None
    return {"step": "business_restored", "at": now.isoformat()}


def retire_confirm_text(name: str, code: str) -> str:
    return (f"🗑 Удалить бизнес «{name}» из активных?\nОплаты, результаты и аудит не удаляются: бизнес уходит в архив "
            f"и его можно вернуть (/business_restore).\nЭто необратимое для работы бота действие, поэтому нужно "
            f"подтверждение (действует {RETIRE_TTL_SECONDS // 60} мин): /business_retire_confirm {code}\n"
            "Отмена: /business_retire_cancel")


def retire_result_text(name: str, *, dry_run: bool) -> str:
    if dry_run:
        return (f"🔒 Удаление бизнеса «{name}» выключено ({RETIRE_ENV}): подтверждение записано, но бизнес остался "
                "активным, ничего не изменено.")
    return f"✅ Бизнес «{name}» удалён из активных. История сохранена: оплаты, результаты и аудит на месте. Вернуть: /business_restore"


__all__ = [
    "RETIRE_ENV",
    "business_restore",
    "is_archived",
    "retire_cancel",
    "retire_confirm",
    "retire_confirm_text",
    "retire_enabled",
    "retire_request",
    "retire_result_text",
    "retire_status",
    "commerce_usage",
    "ACTIVE_CUSTOMER_SKU",
    "STAFF_SEAT_SKU",
    "allowances",
    "commerce_overview",
    "commerce_proposal",
    "commerce_text",
    "expansion_recommended",
    "expansion_request",
    "requested_cases",
    "CANON_BUSINESS_ADMIN_FLOW",
    "audit_lines",
    "State",
    "decide_approval",
    "format_approval",
    "money",
    "parse_money",
    "payment_summary",
    "record_payment",
    "refund_payment",
    "render_summary",
    "replay",
    "request_approval",
    "set_autopilot",
    "set_price",
    "set_setting",
]
