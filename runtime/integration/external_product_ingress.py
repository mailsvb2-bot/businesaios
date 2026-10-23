"""HTTP ingress for signed external-product webhooks.

Read-only pre-authentication (fact replay + HMAC) rejects forged traffic before any decision is
proposed, so attackers cannot make the bot message the owner. Authenticated bodies go through the
sanctioned path: WorldState -> execute_runtime_decision -> business_admin@v1 ``xp_ingest``, whose
handler re-verifies and records the receipt fact (DecisionCore stays the single decision owner)."""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from application.business_flows import external_products as xp
from application.business_flows.projection import flow_payloads
from runtime.decision_gateway import execute_runtime_decision
from runtime.integration.external_product_secrets import resolve_secret_ref
from runtime.messaging_ingress import MessagingIngressEvent, messaging_event_to_world_state

SOURCE = "external_product_webhook"
MAX_BODY = xp.MAX_BODY_BYTES
_HEADERS = ("x-businesaios-timestamp", "x-businesaios-signature")


def preauthenticate(event_store, *, tenant_id: str, connector_id: str, raw_body: bytes, headers: dict[str, str],
                    now_ms: int, vault=None) -> str | None:  # fmt: skip
    """``None`` when authentic, else the rejection code. Never writes."""
    if len(raw_body) > MAX_BODY:
        return "external_product_body_too_large"
    st = xp.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1"))
    c = st.connectors.get(connector_id)
    secret = c and resolve_secret_ref(c.secret_ref, tenant_id=tenant_id, connector_id=connector_id, vault=vault)
    h = {str(k).lower(): str(v) for k, v in headers.items()}
    try:
        xp.authenticate(st, connector_id, secret=secret, timestamp_header=h.get(_HEADERS[0], ""),
                        signature_header=h.get(_HEADERS[1], ""), body=raw_body,
                        now=datetime.fromtimestamp(now_ms / 1000, UTC))  # fmt: skip
    except xp.SignatureError as exc:
        return str(exc)
    return None


def world_state(*, tenant_id: str, owner_user_id: str, connector_id: str, raw_body: bytes,
                headers: dict[str, str], now_ms: int):  # fmt: skip
    base = messaging_event_to_world_state(
        MessagingIngressEvent(channel="telegram", user_id=owner_user_id, chat_id=owner_user_id, tenant_id=tenant_id,
                              timestamp_ms=now_ms)  # fmt: skip
    )
    h = {str(k).lower(): str(v)[:512] for k, v in headers.items() if str(k).lower() in _HEADERS}
    session = {**dict(base.session), "source": SOURCE, "connector_id": connector_id[:64],
               "raw_body": raw_body.decode("utf-8", errors="replace"), "headers": h}  # fmt: skip
    return replace(base, session=session)


def ingest(*, core, executor, event_store, tenant_id: str, owner_user_id: str, connector_id: str, raw_body: bytes,
           headers: dict[str, str], now_ms: int | None = None, vault=None) -> tuple[int, str]:  # fmt: skip
    """Returns (http_status, code). 403 on forged/inactive, 202 after the decision path ran."""
    now = int(now_ms or time.time() * 1000)
    cid = str(connector_id or "").strip()
    if not owner_user_id:
        return 503, "external_product_owner_unconfigured"
    rejected = preauthenticate(event_store, tenant_id=tenant_id, connector_id=cid, raw_body=raw_body,
                               headers=headers, now_ms=now, vault=vault)  # fmt: skip
    if rejected:
        return 403, rejected
    state = world_state(tenant_id=tenant_id, owner_user_id=owner_user_id, connector_id=cid, raw_body=raw_body,
                        headers=headers, now_ms=now)  # fmt: skip
    execute_runtime_decision(issuer=core, executor=executor, state=state)
    return 202, "accepted"


__all__ = ["MAX_BODY", "SOURCE", "ingest", "preauthenticate", "world_state"]
