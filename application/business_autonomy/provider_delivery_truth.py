from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CANON_PROVIDER_DELIVERY_TRUTH = True


def provider_approval_completion_truth(*, provider_key: str, result: Mapping[str, Any]) -> tuple[bool, bool, bool]:
    status = str(result.get("status") or "").strip()
    parsed = dict(result.get("parsed_response") or {})
    error_category = str(dict(result.get("error") or {}).get("category") or "").strip()
    accepted_with_receipt = (
        bool(result.get("accepted"))
        and status == "live_executed"
        and bool(str(parsed.get("resource_id") or "").strip())
    )
    delivered = accepted_with_receipt
    accepted_without_delivery_proof = False
    if str(provider_key) == "whatsapp_cloud" and accepted_with_receipt:
        delivered = False
        accepted_without_delivery_proof = True
    if str(provider_key) == "email_connector" and accepted_with_receipt:
        smtp = dict(dict(result.get("transport_response") or {}).get("smtp") or {})
        delivered = smtp.get("delivered") is True
        accepted_without_delivery_proof = not delivered
    ambiguous = (
        accepted_without_delivery_proof
        or status in {"", "ambiguous_delivery", "in_progress"}
        or status.startswith("provider_queue_")
        or (status == "live_execution_failed" and not bool(parsed.get("error_code")))
        or error_category == "ambiguous_delivery"
    )
    terminal_non_delivery = not delivered and not ambiguous and (
        status in {
            "rejected_misconfigured", "rejected_provider_write_guard",
            "rejected_provider_write_requires_queue", "live_transport_unbound",
            "unsupported_operation",
        }
        or (status == "live_execution_failed" and bool(parsed.get("error_code")))
    )
    return delivered, ambiguous, terminal_non_delivery


__all__ = ["CANON_PROVIDER_DELIVERY_TRUTH", "provider_approval_completion_truth"]
