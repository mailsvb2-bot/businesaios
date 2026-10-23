"""External product connectors (port of clientplatform ``external_products``).

Pure: signed-webhook verification (HMAC-SHA256 over ``"<ts>." + body``, 300 s skew, 64 KB),
strict v1 event parsing, and connector lifecycle as ``business_admin@v1`` facts (``xp_*`` steps).
Connectors hold only a secret *reference*; the runtime resolves it (never stored in facts).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from application.business_flows.projection import stable_id

SIGNATURE_RE = re.compile(r"sha256=([0-9a-fA-F]{64})")
MAX_BODY_BYTES = 64 * 1024
MAX_CLOCK_SKEW_SECONDS = 300
MIN_SECRET_BYTES = 32
EVENT_TYPES = frozenset({"evidence", "lead_created", "lead_qualified", "order_paid", "refund_recorded"})
OBS_STATES = frozenset({"active", "retracted"})
OBS_QUALITY = frozenset({"source_asserted", "source_verified", "derived"})
FEEDBACK = frozenset({"useful", "incorrect", "wrong_customer"})
SOURCES = frozenset(
    {"organic", "referral", "telegram", "vk", "max", "website", "yandex_direct", "partner", "manual_import", "unknown"}
)
_EVENT_KEYS = frozenset(
    {
        "version", "event_id", "type", "occurred_at", "customer_ref", "subject_ref", "related_event_id",
        "amount_minor", "currency", "acquisition", "observation", "metadata",
    }
)  # fmt: skip
_OBS_KEYS = frozenset(
    {
        "observation_key", "kind", "label", "observed_at", "provenance_ref", "revision", "state",
        "supersedes_external_event_id", "fresh_until", "quality", "limitations",
    }
)  # fmt: skip
_REF = re.compile(r"^(env|vault):[A-Za-z0-9_.\-]{1,120}$")


class SignatureError(ValueError):
    """Webhook authentication failed (stable reason code, never secret material)."""


@dataclass
class Connector:
    connector_id: str
    product_key: str
    display_name: str
    secret_ref: str
    status: str = "pending"  # pending | active | disabled
    bindings: dict[str, str] = field(default_factory=dict)  # customer_ref -> customer_id


@dataclass
class State:
    connectors: dict[str, Connector] = field(default_factory=dict)
    receipts: dict[str, dict[str, Any]] = field(default_factory=dict)  # receipt_id -> fact
    feedback: dict[str, str] = field(default_factory=dict)


def replay(payloads: list[dict[str, Any]]) -> State:
    st = State()
    for p in payloads:
        step, cid = p.get("step"), str(p.get("connector_id") or "")
        c = st.connectors.get(cid)
        if step == "xp_provisioned":
            st.connectors[cid] = Connector(cid, p["product_key"], p["display_name"], p["secret_ref"])
        elif step in ("xp_activated", "xp_disabled") and c:
            c.status = "active" if step == "xp_activated" else "disabled"
        elif step == "xp_bound" and c:
            c.bindings[p["customer_ref"]] = p["customer_id"]
        elif step == "xp_event":
            st.receipts[p["receipt_id"]] = p
        elif step == "xp_feedback" and p.get("receipt_id") in st.receipts:
            st.feedback[p["receipt_id"]] = p["feedback"]
    return st


def _get(st: State, connector_id: str) -> Connector:
    c = st.connectors.get(str(connector_id or "").strip())
    if c is None:
        raise ValueError("коннектор не найден")
    return c


def provision(st: State, *, product_key: str, display_name: str, secret_ref: str) -> dict[str, Any]:
    """Donor ``provision_external_product_connector``: pending connector with a secret reference only."""
    key = str(product_key or "").strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", key):
        raise ValueError("product_key: латиница/цифры/_, 2..64")
    if not _REF.fullmatch(str(secret_ref or "")):
        raise ValueError("нужна ссылка на секрет env:NAME или vault:NAME — сам секрет в чат не передавайте")
    cid = stable_id("xp", key)
    if cid in st.connectors and st.connectors[cid].status != "disabled":
        raise ValueError("коннектор уже есть")
    name = " ".join(str(display_name or key).split())[:120]
    return {
        "step": "xp_provisioned",
        "connector_id": cid,
        "product_key": key,
        "display_name": name,
        "secret_ref": secret_ref,
    }


def activate(st: State, connector_id: str, *, secret: str | None) -> dict[str, Any]:
    """Donor ``verify_and_activate_external_product_connector``: only with a resolvable ≥32-byte secret."""
    c = _get(st, connector_id)
    if secret is None:
        raise ValueError("секрет вебхука недоступен")
    if len(secret.encode("utf-8")) < MIN_SECRET_BYTES:
        raise ValueError("секрет вебхука должен быть не короче 32 байт")
    return {"step": "xp_activated", "connector_id": c.connector_id}


def bind(st: State, connector_id: str, *, customer_id: str, customer_ref: str) -> dict[str, Any]:
    """Donor ``bind_external_product_customer``: explicit server-side binding (webhook cannot set identity)."""
    c = _get(st, connector_id)
    ref, cust = str(customer_ref or "").strip()[:200], str(customer_id or "").strip()[:200]
    if not ref or not cust:
        raise ValueError("нужны customer_ref и customer_id")
    if c.bindings.get(ref) not in (None, cust):
        raise ValueError("customer_ref уже привязан к другому клиенту")
    return {"step": "xp_bound", "connector_id": c.connector_id, "customer_ref": ref, "customer_id": cust}


def disable(st: State, connector_id: str) -> dict[str, Any]:
    return {"step": "xp_disabled", "connector_id": _get(st, connector_id).connector_id}


def record_feedback(st: State, receipt_id: str, feedback: str) -> dict[str, Any]:
    """Donor ``record_external_observation_feedback``: value-proof signal, never an identity mutation."""
    if receipt_id not in st.receipts:
        raise ValueError("квитанция не найдена")
    fb = str(feedback or "").strip().lower()
    if fb not in FEEDBACK:
        raise ValueError("оценка: useful | incorrect | wrong_customer")
    return {"step": "xp_feedback", "receipt_id": receipt_id, "feedback": fb}


def value_snapshot(st: State, connector_id: str | None = None) -> dict[str, int]:
    """Donor ``get_external_observation_value_snapshot`` (accepted observations + feedback counts)."""
    rec = [r for r in st.receipts.values() if connector_id in (None, r["connector_id"])]
    obs = [r for r in rec if r.get("observation")]
    fb = [st.feedback[r["receipt_id"]] for r in rec if r["receipt_id"] in st.feedback]
    return {
        "events": len(rec),
        "observations": len(obs),
        "active_observations": sum(1 for r in obs if r["observation"]["state"] == "active"),
        "feedback_total": len(fb),
        "useful_feedback": fb.count("useful"),
        "incorrect_feedback": fb.count("incorrect"),
        "wrong_customer_feedback": fb.count("wrong_customer"),
    }


def verify_signature(*, secret: str, timestamp_header: str, signature_header: str, body: bytes, now: datetime) -> None:
    """Donor ``verify_external_product_signature`` (same order of checks and reason codes)."""
    key = str(secret or "").encode("utf-8")
    if len(key) < MIN_SECRET_BYTES:
        raise SignatureError("external_product_secret_invalid")
    raw_ts = str(timestamp_header or "").strip()
    try:
        ts = int(raw_ts)
    except (TypeError, ValueError):
        raise SignatureError("external_product_timestamp_invalid") from None
    if now.tzinfo is None:
        raise ValueError("signature verification clock must be timezone-aware")
    if abs(int(now.timestamp()) - ts) > MAX_CLOCK_SKEW_SECONDS:
        raise SignatureError("external_product_timestamp_expired")
    m = SIGNATURE_RE.fullmatch(str(signature_header or "").strip())
    if m is None:
        raise SignatureError("external_product_signature_invalid")
    if len(body) > MAX_BODY_BYTES:
        raise SignatureError("external_product_body_too_large")
    expected = hmac.new(key, raw_ts.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(m.group(1).lower(), expected):
        raise SignatureError("external_product_signature_invalid")


def _parse_occurred_at(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 80:
        raise ValueError("external product occurred_at is invalid")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("external product occurred_at is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("external product occurred_at must include a timezone")
    return parsed.astimezone(UTC).isoformat()


def _opt(v: Any) -> str | None:
    return None if v is None else str(v)


def _parse_observation(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("external product observation must be an object")
    if set(value) - _OBS_KEYS:
        raise ValueError("external product observation contains unsupported fields")
    lim = value.get("limitations") or []
    if not isinstance(lim, list) or any(not isinstance(x, str) for x in lim):
        raise ValueError("external product observation limitations must be strings")
    rev = value.get("revision", 1)
    if isinstance(rev, bool) or not isinstance(rev, int):
        raise ValueError("external product observation revision must be an integer")
    state = str(value.get("state") or "active").strip().lower()
    quality = str(value.get("quality") or "source_asserted").strip().lower()
    if state not in OBS_STATES or quality not in OBS_QUALITY:
        raise ValueError("external product observation state/quality is invalid")
    return {
        "observation_key": str(value.get("observation_key") or ""),
        "kind": str(value.get("kind") or ""),
        "label": str(value.get("label") or ""),
        "observed_at": _parse_occurred_at(value.get("observed_at")),
        "provenance_ref": str(value.get("provenance_ref") or ""),
        "revision": rev,
        "state": state,
        "supersedes_external_event_id": _opt(value.get("supersedes_external_event_id")),
        "fresh_until": None if value.get("fresh_until") is None else _parse_occurred_at(value["fresh_until"]),
        "quality": quality,
        "limitations": list(lim),
    }


def _parse_money(payload: dict[str, Any], *, event_type: str) -> dict[str, Any] | None:
    has_a, has_c = "amount_minor" in payload, "currency" in payload
    if has_a != has_c:
        raise ValueError("external product money requires amount_minor and currency")
    if not has_a:
        return None
    amount = payload.get("amount_minor")
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise ValueError("external product amount_minor must be an integer")
    if event_type in ("order_paid", "refund_recorded") and amount < 0:
        raise ValueError(f"external product {event_type} amount must not be negative")
    return {"amount_minor": amount, "currency": str(payload.get("currency") or "")}


def _parse_acquisition(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {"source", "source_key"}:
        raise ValueError("external product acquisition is invalid")
    src = str(value.get("source") or "").strip().lower()
    if src not in SOURCES:
        raise ValueError("external product acquisition is invalid")
    return {"source": src, "source_key": str(value.get("source_key") or "")}


def parse_event(body: bytes) -> dict[str, Any]:
    """Donor ``parse_external_product_event``: strict schema v1, unknown keys rejected."""
    if not body or len(body) > MAX_BODY_BYTES:
        raise ValueError("external product body must be 1..65536 bytes")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("external product body must be valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("external product body must be a JSON object")
    if set(payload) - _EVENT_KEYS:
        raise ValueError("external product body contains unsupported fields")
    if payload.get("version") != 1:
        raise ValueError("external product event version must be 1")
    occurred = _parse_occurred_at(payload.get("occurred_at"))
    etype = str(payload.get("type") or "").strip()
    if etype not in EVENT_TYPES:
        raise ValueError("external product event type is invalid")
    meta = payload.get("metadata") or {}
    if not isinstance(meta, dict):
        raise ValueError("external product metadata must be an object")
    eid = str(payload.get("event_id") or "").strip()
    if not eid or len(eid) > 200:
        raise ValueError("external product event_id is invalid")
    return {
        "external_event_id": eid,
        "event_type": etype,
        "occurred_at": occurred,
        "customer_ref": _opt(payload.get("customer_ref")),
        "subject_ref": _opt(payload.get("subject_ref")),
        "related_event_id": _opt(payload.get("related_event_id")),
        "money": _parse_money(payload, event_type=etype),
        "acquisition": _parse_acquisition(payload.get("acquisition")),
        "observation": _parse_observation(payload.get("observation")),
        "metadata": meta,
    }


def authenticate(
    st: State, connector_id: str, *, secret: str | None, timestamp_header: str, signature_header: str, body: bytes,
    now: datetime,
) -> tuple[Connector, str]:  # fmt: skip
    """Donor ``authenticate_external_product_webhook``: active connector + verified bytes -> fingerprint."""
    c = st.connectors.get(str(connector_id or ""))
    if c is None or c.status != "active":
        raise SignatureError("external_product_connector_inactive")
    if secret is None:
        raise SignatureError("external_product_secret_unavailable")
    verify_signature(
        secret=secret, timestamp_header=timestamp_header, signature_header=signature_header, body=body, now=now
    )
    return c, hashlib.sha256(body).hexdigest()


def ingest_authenticated(st: State, c: Connector, event: dict[str, Any], *, fingerprint: str, received_at: str):
    """Donor ``ingest_authenticated_external_product_event``: idempotent per (connector, event_id).

    Returns (fact | None, receipt_id); a replay with a different payload is rejected.
    """
    rid = stable_id("xpr", f"{c.connector_id}:{event['external_event_id']}")
    old = st.receipts.get(rid)
    if old is not None:
        if old["payload_fingerprint"] != fingerprint:
            raise ValueError("external product event_id reused with a different payload")
        return None, rid
    customer = c.bindings.get(event["customer_ref"] or "", "")
    fact = {
        "step": "xp_event", "receipt_id": rid, "connector_id": c.connector_id, "payload_fingerprint": fingerprint,
        "received_at": received_at, "customer_id": customer, **event,
    }  # fmt: skip
    return fact, rid


def ingest_webhook(
    st: State, connector_id: str, *, secret: str | None, timestamp_header: str, signature_header: str, body: bytes,
    now: datetime,
):  # fmt: skip
    """Donor ``ingest_external_product_webhook``: authenticate, parse, then ingest."""
    c, fp = authenticate(
        st, connector_id, secret=secret, timestamp_header=timestamp_header, signature_header=signature_header,
        body=body, now=now,
    )  # fmt: skip
    return ingest_authenticated(st, c, parse_event(body), fingerprint=fp, received_at=now.astimezone(UTC).isoformat())
