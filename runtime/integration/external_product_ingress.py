"""HTTP ingress for signed external-product webhooks.

Read-only pre-authentication (fact replay + HMAC) rejects forged traffic before any decision is
proposed, so attackers cannot make the bot message the owner. Authenticated bodies go through the
sanctioned path: WorldState -> execute_runtime_decision -> business_admin@v1 ``xp_ingest``, whose
handler re-verifies and records the receipt fact (DecisionCore stays the single decision owner)."""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import UTC, datetime

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
    st = xp.replay(flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1"), discover=True)
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
                headers: dict[str, str], now_ms: int, business_id: str = ""):  # fmt: skip
    base = messaging_event_to_world_state(
        MessagingIngressEvent(channel="telegram", user_id=owner_user_id, chat_id=owner_user_id, tenant_id=tenant_id,
                              timestamp_ms=now_ms)  # fmt: skip
    )
    h = {str(k).lower(): str(v)[:512] for k, v in headers.items() if str(k).lower() in _HEADERS}
    session = {**dict(base.session), "source": SOURCE, "connector_id": connector_id[:64],
               "raw_body": raw_body.decode("utf-8", errors="strict"), "headers": h, "xp_business_id": business_id}  # fmt: skip
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
    connectors = xp.replay(
        flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1"), discover=True
    )
    connector = connectors.connectors.get(cid)
    if connector is None:
        return 403, "external_product_connector_inactive"
    try:
        xp.parse_event(raw_body)
    except (ValueError, UnicodeError):
        return 422, "external_product_schema_invalid"
    state = world_state(tenant_id=tenant_id, owner_user_id=owner_user_id, connector_id=cid, raw_body=raw_body,
                        headers=headers, now_ms=now, business_id=connector.business_id)  # fmt: skip
    execute_runtime_decision(issuer=core, executor=executor, state=state)
    return 202, "accepted"


def ingest_uiii_proof(
    *, core, executor, event_store, tenant_id: str, owner_user_id: str,
    connector_id: str, compact_jws: str, context, verified_keys,
    now_ms: int | None = None, vault=None,
) -> tuple[int, str]:
    """Trusted internal bridge: pinned JWS proof -> existing signed XP ingress.

    Caller must supply a server-authorized MappingContext and canonical pinned
    key registry; no public client may supply either. This function creates no
    new decision or store and fails closed on unbound customer/connection scope.
    """
    from interfaces.uiii.signals import (
        SignalRejected, to_external_product_event, verify_signal, xp_headers,
    )

    now = int(now_ms if now_ms is not None else time.time() * 1000)
    when = datetime.fromtimestamp(now / 1000, UTC)
    if tenant_id != context.tenant_id or connector_id != context.connection_id:
        return 403, "uiii_connection_scope_mismatch"
    st = xp.replay(
        flow_payloads(event_store, tenant_id=tenant_id, event_type="business_admin@v1"),
        discover=True,
    )
    connector = st.connectors.get(connector_id)
    if (
        connector is None or connector.status != "active"
        or connector.business_id != context.business_id
        or not connector.bindings.get(context.customer_ref)
    ):
        return 403, "uiii_customer_or_business_binding_missing"
    secret = resolve_secret_ref(
        connector.secret_ref, tenant_id=tenant_id,
        connector_id=connector_id, vault=vault,
    )
    if not secret or len(secret.encode("utf-8")) < xp.MIN_SECRET_BYTES:
        return 503, "uiii_connector_secret_unavailable"
    try:
        verified = verify_signal(compact_jws, context=context, keys=verified_keys, now=when)
        body = to_external_product_event(
            verified, context=context, keys=verified_keys, now=when,
        )
        headers = xp_headers(body, secret=secret.encode("utf-8"), now=when)
    except SignalRejected as exc:
        return 403, str(exc)
    return ingest(
        core=core, executor=executor, event_store=event_store,
        tenant_id=tenant_id, owner_user_id=owner_user_id,
        connector_id=connector_id, raw_body=body, headers=headers,
        now_ms=now, vault=vault,
    )


__all__ = ["MAX_BODY", "SOURCE", "ingest", "ingest_uiii_proof", "preauthenticate", "world_state"]
