"""Explicit UCR attendance pilot: one verified attendance snapshot -> external-product evidence fact.

Port of donor ``application/ucr_attendance_pilot``. Manual/trusted-pull boundary only: no
background polling, no Sales/Outcome facts, no CRM stage changes, no messages. The customer
reference must already be bound on an *active* connector. Returns the ``xp_event`` fact for the
caller to append through the executor (``business_admin`` facts stream); nothing is written here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from application.business_flows import external_products as xp
from interfaces.ucr.attendance import (
    AttendanceObservation,
    ObservationHead,
    UcrAttendanceGateway,
    read_ucr_attendance_observation,
)


def received_at(value: datetime | None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("UCR attendance pilot received_at must be timezone-aware")
    return current.astimezone(UTC)


def event_id(*, observation_key: str, provenance_ref: str, revision: int) -> str:
    digest = hashlib.sha256(f"{observation_key}\x00{provenance_ref}".encode()).hexdigest()[:40]
    return f"ucr-attendance:{digest}:r{revision}"


def customer_fingerprint(*, connector_id: str, customer_ref: str) -> str:
    return hashlib.sha256(f"{connector_id}\x00{customer_ref}".encode()).hexdigest()


def _observation(o: AttendanceObservation) -> dict[str, Any]:
    return {
        "observation_key": o.observation_key, "kind": o.kind, "label": o.label,
        "observed_at": o.observed_at.astimezone(UTC).isoformat(), "provenance_ref": o.provenance_ref,
        "revision": o.revision, "state": "active", "supersedes_external_event_id": o.supersedes_external_event_id,
        "fresh_until": None, "quality": o.quality, "limitations": list(o.limitations),
    }  # fmt: skip


def payload_fingerprint(*, connector_id: str, customer_ref: str, event: Mapping[str, Any]) -> str:
    observation = event.get("observation")
    if not observation:
        raise ValueError("UCR attendance pilot event requires an observation")
    payload = {
        "connector_id": connector_id,
        "customer_fingerprint": customer_fingerprint(connector_id=connector_id, customer_ref=customer_ref),
        "external_event_id": event["external_event_id"],
        "occurred_at": event["occurred_at"],
        "observation": observation,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def current_head(st: xp.State, *, connector_id: str, customer_id: str, observation_key: str) -> dict[str, Any] | None:
    """Latest-revision receipt for (connector, customer, observation key)."""
    best = None
    for r in st.receipts.values():
        o = r.get("observation") or {}
        if (r.get("connector_id"), r.get("customer_id"), o.get("observation_key")) != (
            connector_id,
            customer_id,
            observation_key,
        ):
            continue
        if best is None or int(o.get("revision") or 0) > int(best["observation"].get("revision") or 0):
            best = r
    return best


def _bound_active(st: xp.State, connector_id: str, *, customer_id: str, customer_ref: str) -> xp.Connector:
    c = st.connectors.get(str(connector_id or "").strip())
    if c is None or c.status != "active":
        raise ValueError("trusted pull connector is not active")
    bound = c.bindings.get(customer_ref)
    if bound is None:
        raise ValueError("trusted pull customer reference is not bound")
    if bound != customer_id:
        raise ValueError("trusted pull customer reference belongs to another customer")
    return c


async def sync_ucr_attendance_pilot(
    st: xp.State, *, connector_id: str, customer_id: str, customer_ref: str, canonical_request: Mapping[str, Any],
    observation_key: str, gateway: UcrAttendanceGateway, received: datetime | None = None,
) -> dict[str, Any]:  # fmt: skip
    """Returns ``{attendance, fact, receipt_id, persisted}``; ``fact`` is None when nothing new."""
    customer_id, key = str(customer_id or "").strip(), str(observation_key or "").strip()
    if not customer_id or not key:
        raise ValueError("customer_id and observation_key are required")
    at = received_at(received)
    c = _bound_active(st, connector_id, customer_id=customer_id, customer_ref=customer_ref)
    head = current_head(st, connector_id=c.connector_id, customer_id=customer_id, observation_key=key)
    head_obj = None if head is None else ObservationHead(
        key, int(head["observation"].get("revision") or 0) or None, str(head["external_event_id"])
    )  # fmt: skip
    read = await read_ucr_attendance_observation(
        gateway=gateway, canonical_request=canonical_request, observation_key=key, current_head=head_obj
    )
    out: dict[str, Any] = {"attendance": read.attendance, "fact": None, "receipt_id": None, "persisted": False}
    o = read.observation
    if o is None:
        return out
    if head is not None and head["observation"].get("provenance_ref") == o.provenance_ref:
        return {**out, "receipt_id": head["receipt_id"]}
    event = {
        "external_event_id": event_id(observation_key=key, provenance_ref=o.provenance_ref,
                                                    revision=o.revision),
        "event_type": "evidence", "occurred_at": o.observed_at.astimezone(UTC).isoformat(), "customer_ref": customer_ref,
        "subject_ref": None, "related_event_id": None, "money": None, "acquisition": None,
        "observation": _observation(o), "metadata": {"source_adapter": "ucr_attendance_pilot"},
    }  # fmt: skip
    fp = payload_fingerprint(connector_id=c.connector_id, customer_ref=customer_ref, event=event)
    fact, rid = xp.ingest_authenticated(st, c, event, fingerprint=fp, received_at=at.isoformat())
    return {**out, "fact": fact, "receipt_id": rid, "persisted": fact is not None}


__all__ = ["current_head", "event_id", "payload_fingerprint", "received_at", "sync_ucr_attendance_pilot"]
