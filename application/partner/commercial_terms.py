"""Owner-governed, event-sourced partner commercial proposals.

These records are *drafts and internal approvals*, not legal agreements,
provider sends, payment authorizations or spend commitments. The partner's
acceptance must be verified separately before an agreement can be executed.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

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
        elif step in {"partner_quote_approved", "partner_quote_rejected"} and quote_id in states:
            if states[quote_id]["status"] == "pending_owner_approval":
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
            f" · {quote['status']}\nУсловия: {quote['scope']}")
