from __future__ import annotations

import asyncio
import hashlib
import re
import time
from typing import Any

from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget, estimate_request_tokens, has_durable_budget_store, validated_llm_usage
from core.marketing.llm_telemetry import append_event_sync
from core.telemetry.event_types import LLM_COMPLETED, LLM_REQUESTED
from core.telemetry.event_writer import TelemetryContext


_EVENT_METADATA_KEYS = (
    "channel", "locale", "kind", "message_id", "offer_id", "experiment", "variant",
    "prompt_version", "prompt_hash", "task_type", "model_profile_id", "model_version",
    "model_policy_id", "model_policy_version", "model_fallback_from_profile_id",
)


class AccountedSyncGateway:
    """Single durable boundary for budget reservation, provider execution and usage."""

    def __init__(self, client: Any, *, event_store: Any, provider: str, budget: Any = None) -> None:
        self._client, self._store = client, event_store
        self._provider = str(provider or "").strip()
        if not self._provider:
            raise ValueError("LLM_PROVIDER_ID_REQUIRED")
        if budget is not None and not isinstance(budget, EventStoreDailyTokenBudget):
            raise ValueError("LLM_BUDGET_OWNER_INVALID")
        if budget is not None and getattr(budget, "_es", None) is not event_store:
            raise ValueError("LLM_BUDGET_STORE_MISMATCH")
        self._budget = budget or EventStoreDailyTokenBudget(
            event_store=event_store, caps=BudgetCaps(),
        )

    @staticmethod
    def _event_metadata(meta: dict[str, Any]) -> dict[str, str]:
        result: dict[str, str] = {}
        for key in _EVENT_METADATA_KEYS:
            value = meta.get(key)
            if isinstance(value, str) and value.strip() and len(value) <= 512:
                result[key] = value
        return result

    @staticmethod
    def _provider_call(client: Any, request: Any) -> Any:
        generate_sync = getattr(client, "generate_sync", None)
        if callable(generate_sync):
            return generate_sync(request)
        generate = getattr(client, "generate", None)
        if callable(generate):
            # Called from the gateway's worker thread when used asynchronously.
            return asyncio.run(generate(request))
        raise RuntimeError("LLM_PROVIDER_INTERFACE_UNAVAILABLE")

    def generate_sync(self, request: Any) -> Any:
        raw_meta = getattr(request, "metadata", None)
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        tenant = str(meta.get("tenant_id") or "").strip()
        user = str(meta.get("user_id") or "").strip()
        correlation = str(meta.get("correlation_key") or "").strip()
        task = str(meta.get("task_type") or "").strip()
        model = str(getattr(request, "model", "") or "").strip()
        if not all((tenant, user, correlation, task, model)) or not has_durable_budget_store(self._store):
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE")

        supplied_request_id = meta.get("request_id")
        if supplied_request_id is None:
            identity = hashlib.sha256("\0".join((tenant, user, correlation, task, model)).encode()).hexdigest()[:32]
            request_id = f"llm-gateway-{identity}"
        elif isinstance(supplied_request_id, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", supplied_request_id):
            request_id = supplied_request_id
        else:
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE")

        try:
            day = self._budget.reserve(
                tenant_id=tenant,
                user_id=user,
                tokens=estimate_request_tokens(request),
                request_id=request_id,
            )
        except Exception as exc:
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE") from exc
        if day is None:
            raise RuntimeError("LLM_BUDGET_BLOCKED")

        ctx = TelemetryContext(
            tenant_id=tenant,
            user_id=user,
            message_id=str(meta.get("message_id") or ""),
            correlation_id=correlation,
        )
        event_metadata = self._event_metadata(meta)
        try:
            append_event_sync(
                event_store=self._store,
                event_type=LLM_REQUESTED,
                ctx=ctx,
                required=True,
                payload={
                    "request_id": request_id,
                    "provider": self._provider,
                    "model": model,
                    **event_metadata,
                },
            )
        except Exception as exc:
            try:
                cancelled = self._budget.cancel_unstarted_reservation(
                    tenant_id=tenant, request_id=request_id, day=day,
                )
            except Exception as cancel_exc:
                raise RuntimeError("LLM_ACCOUNTING_RESERVATION_CANCEL_FAILED") from cancel_exc
            if not cancelled:
                raise RuntimeError("LLM_ACCOUNTING_RESERVATION_CANCEL_FAILED") from exc
            raise RuntimeError("LLM_ACCOUNTING_REQUEST_WRITE_FAILED") from exc

        started = time.monotonic()
        response = self._provider_call(self._client, request)
        usage = validated_llm_usage(getattr(response, "usage", None))
        if usage is None:
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE")
        prompt, completion, total = usage
        try:
            append_event_sync(
                event_store=self._store,
                event_type=LLM_COMPLETED,
                ctx=ctx,
                required=True,
                payload={
                    "request_id": request_id,
                    "provider": self._provider,
                    "model": model,
                    "prompt_tokens": prompt,
                    "completion_tokens": completion,
                    "total_tokens": total,
                    "latency_ms": max(0, int((time.monotonic() - started) * 1000)),
                    "finish_reason": str(getattr(response, "finish_reason", "") or ""),
                    "cache_hit": False,
                    "ok": True,
                    "error_code": "",
                    **event_metadata,
                },
            )
        except Exception as exc:
            raise RuntimeError("LLM_ACCOUNTING_COMPLETION_WRITE_FAILED") from exc
        if not self._budget.release(tenant_id=tenant, request_id=request_id, day=day):
            raise RuntimeError("LLM_ACCOUNTING_RESERVATION_RELEASE_FAILED")
        return response

    async def generate(self, request: Any) -> Any:
        return await asyncio.to_thread(self.generate_sync, request)
