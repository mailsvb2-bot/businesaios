from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from reliability.idempotency_contract import IdempotencyResolution
from reliability.idempotency_scope import build_idempotency_key

CANON_PROCESS_REQUEST_IDEMPOTENCY = True


class ProcessRequestIdempotencyError(RuntimeError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class ProcessRequestLease:
    key: object
    replay_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProcessRequestIdempotency:
    """Reliability adapter only; it never plans or executes business actions."""

    store: Any
    namespace: str = "interfaces.api.process_workspace"
    owner_id: str = "api-process-workspace-idempotency"

    def begin(
        self, *, tenant_id: str, operation: str, raw_key: str, semantic_scope: Mapping[str, Any]
    ) -> ProcessRequestLease:
        key_text = str(raw_key or "").strip()
        if not key_text:
            raise ProcessRequestIdempotencyError("api_replay_protection_required", 403)
        if self.store is None:
            raise ProcessRequestIdempotencyError("process_idempotency_store_unavailable", 503)
        key = build_idempotency_key(
            tenant_id=tenant_id, namespace=self.namespace, operation=operation, key=key_text,
            semantic_scope=dict(semantic_scope),
        )
        decision = self.store.reserve(
            key=key, owner_id=self.owner_id,
            metadata_patch={"surface": "business_workspace_process", "operation": operation},
        )
        if decision.resolution is IdempotencyResolution.ACCEPTED:
            return ProcessRequestLease(key=key)
        if decision.resolution is IdempotencyResolution.REPLAY_COMPLETED:
            payload = dict(getattr(decision.record, "metadata", {}) or {}).get("response_payload")
            if not isinstance(payload, Mapping):
                raise ProcessRequestIdempotencyError("process_idempotency_replay_payload_missing", 409)
            return ProcessRequestLease(key=key, replay_payload=dict(payload))
        codes = {
            IdempotencyResolution.REJECTED_IN_PROGRESS: "idempotency_in_progress",
            IdempotencyResolution.REJECTED_SCOPE_MISMATCH: "idempotency_scope_mismatch",
            IdempotencyResolution.REJECTED_TERMINAL_FAILED: "idempotency_terminal_failed",
        }
        raise ProcessRequestIdempotencyError(codes.get(decision.resolution, "idempotency_rejected"), 409)

    def complete(self, *, lease: ProcessRequestLease, payload: Mapping[str, Any]) -> None:
        self.store.mark_completed(
            key=lease.key, owner_id=self.owner_id,
            metadata_patch={"response_payload": dict(payload)},
        )

    def fail(self, *, lease: ProcessRequestLease, reason: str) -> None:
        self.store.mark_failed(key=lease.key, owner_id=self.owner_id, reason=str(reason or "process_request_failed"))


__all__ = [
    "CANON_PROCESS_REQUEST_IDEMPOTENCY", "ProcessRequestIdempotency",
    "ProcessRequestIdempotencyError", "ProcessRequestLease",
]
