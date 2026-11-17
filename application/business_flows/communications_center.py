"""Web communications center (P1-22): one read-only view over existing owners.

Inbound = canonical Message registry (direction inbound). Outbound / failed =
provider sync history of ``message_send`` judged only by
``provider_approval_completion_truth`` (a provider receipt, never our wish).
Queue / retries = provider queue jobs of ``message_send`` (attempts > 0 is a
retry). Pending approvals stay with the existing approvals API. No writes, no
sender, no second decision owner.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from application.business_autonomy.provider_delivery_truth import provider_approval_completion_truth

CANON_COMMUNICATIONS_CENTER = True
LIMIT = 50


def inbound_rows(messages: Iterable[Any]) -> list[dict[str, Any]]:
    rows = [{"message_id": m.message_id, "channel": m.channel, "customer_id": m.customer_id or "",
             "conversation_id": m.conversation_id or "", "at_ms": int(m.created_at_ms or 0)}
            for m in messages if str(getattr(m.direction, "value", m.direction)) == "inbound"]
    return sorted(rows, key=lambda r: -r["at_ms"])[:LIMIT]


def outbound_rows(provider_key: str, history: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in history:
        if str(row.get("operation") or "") != "message_send" or str(row.get("mode") or "live") != "live":
            continue
        delivered, ambiguous, terminal = provider_approval_completion_truth(provider_key=provider_key, result=row)
        error = dict(row.get("error") or {})
        out.append({
            "provider_key": provider_key,
            "state": "delivered" if delivered else "failed" if terminal else "unconfirmed",
            "receipt": str(dict(row.get("parsed_response") or {}).get("resource_id") or "") if delivered else "",
            "reason": "" if delivered else str(error.get("category") or row.get("status") or ""),
            "at": str(row.get("recorded_at_utc") or ""),
            "queue_job_id": str(row.get("queue_job_id") or ""),
        })
    return out


def queue_rows(provider_key: str, jobs: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for job in jobs:
        payload = dict(job.get("payload") or {})
        if str(payload.get("operation") or "") != "message_send" or str(job.get("state") or "") not in {"pending", "claimed"}:
            continue
        out.append({"provider_key": provider_key, "job_id": str(job.get("job_id") or ""),
                    "attempts": int(job.get("attempts") or 0), "run_at": str(job.get("run_at") or "")})
    return out


def build(*, messages: Iterable[Any], providers: Mapping[str, tuple[Iterable[Mapping[str, Any]], Iterable[Mapping[str, Any]]]]) -> dict[str, Any]:
    """``providers``: provider_key -> (sync history rows, queue jobs)."""
    outbound, queued = [], []
    for key, (history, jobs) in sorted(providers.items()):
        outbound += outbound_rows(key, history)
        queued += queue_rows(key, jobs)
    outbound.sort(key=lambda r: r["at"], reverse=True)
    view = {
        "inbound": inbound_rows(messages),
        "outbound": [r for r in outbound if r["state"] == "delivered"][:LIMIT],
        "unconfirmed": [r for r in outbound if r["state"] == "unconfirmed"][:LIMIT],
        "failed": [r for r in outbound if r["state"] == "failed"][:LIMIT],
        "queued": [r for r in queued if r["attempts"] == 0][:LIMIT],
        "retries": [r for r in queued if r["attempts"] > 0][:LIMIT],
        "pending_approval_source": "/control-plane/approvals/open",
    }
    view["counts"] = {k: len(v) for k, v in view.items() if isinstance(v, list)}
    return view


__all__ = ["CANON_COMMUNICATIONS_CENTER", "build", "inbound_rows", "outbound_rows", "queue_rows"]
