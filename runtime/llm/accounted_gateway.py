from __future__ import annotations

import hashlib
from typing import Any

from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget, estimate_request_tokens, has_durable_budget_store, provider_reported_usage
from core.marketing.llm_telemetry import append_event_sync
from core.telemetry.event_types import LLM_COMPLETED, LLM_REQUESTED
from core.telemetry.event_writer import TelemetryContext


class AccountedSyncGateway:
    """Shared durable provider boundary for task agents and sealed effects."""

    def __init__(self, client: Any, *, event_store: Any, provider: str) -> None:
        self._client, self._store, self._provider = client, event_store, str(provider)

    def generate_sync(self, request: Any) -> Any:
        meta = request.metadata or {}
        tenant = str(meta.get("tenant_id") or "").strip()
        user = str(meta.get("user_id") or "").strip()
        correlation = str(meta.get("correlation_key") or "").strip()
        task = str(meta.get("task_type") or "").strip()
        if not all((tenant, user, correlation, task)) or not has_durable_budget_store(self._store):
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE")
        identity = hashlib.sha256("\0".join((tenant, user, correlation, task, request.model)).encode()).hexdigest()[:32]
        request_id = f"llm-gateway-{identity}"
        budget = EventStoreDailyTokenBudget(event_store=self._store, caps=BudgetCaps())
        day = budget.reserve(tenant_id=tenant, user_id=user, tokens=estimate_request_tokens(request), request_id=request_id)
        if day is None:
            raise RuntimeError("LLM_BUDGET_BLOCKED")
        ctx = TelemetryContext(tenant_id=tenant, user_id=user, message_id=correlation, correlation_id=correlation)
        try:
            append_event_sync(event_store=self._store, event_type=LLM_REQUESTED, ctx=ctx,
                              required=True, payload={"request_id": request_id, "provider": self._provider, "model": request.model})
        except Exception as exc:
            budget.cancel_unstarted_reservation(tenant_id=tenant, request_id=request_id, day=day)
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE") from exc
        response = self._client.generate_sync(request)
        usage = getattr(response, "usage", None)
        try:
            prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion = int(getattr(usage, "completion_tokens", 0) or 0)
            reported = int(getattr(usage, "total_tokens", 0) or 0)
            if min(prompt, completion, reported) < 0 or max(prompt + completion, reported) == 0:
                raise ValueError("missing or invalid provider token usage")
        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            # Provider may have billed us: keep the claim, never fabricate actual usage.
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE") from exc
        total = max(prompt + completion, reported)
        try:
            append_event_sync(event_store=self._store, event_type=LLM_COMPLETED, ctx=ctx, required=True,
                              payload={"request_id": request_id, "provider": self._provider, "model": request.model,
                                       "prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total})
        except Exception as exc:
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE") from exc
        if not budget.release(tenant_id=tenant, request_id=request_id, day=day):
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE")
        return response
