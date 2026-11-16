from __future__ import annotations

import asyncio
import hashlib
import re
import time
from typing import Any

from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget, estimate_request_tokens, has_durable_budget_store, validated_llm_usage
from core.marketing.llm_telemetry import append_event_sync
from core.telemetry.event_types import LLM_BUDGET_BLOCKED, LLM_COMPLETED, LLM_REQUESTED
from core.telemetry.event_writer import TelemetryContext

_METADATA_KEYS = (
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
        if budget is not None and (
            not isinstance(budget, EventStoreDailyTokenBudget) or getattr(budget, "_es", None) is not event_store
        ):
            raise ValueError("LLM_BUDGET_STORE_MISMATCH")
        self._budget = budget or EventStoreDailyTokenBudget(event_store=event_store, caps=BudgetCaps())

    @staticmethod
    def _provider_call(client: Any, request: Any) -> Any:
        if callable(sync := getattr(client, "generate_sync", None)):
            return sync(request)
        if callable(generate := getattr(client, "generate", None)):
            return asyncio.run(generate(request))
        raise RuntimeError("LLM_PROVIDER_INTERFACE_UNAVAILABLE")

    def generate_sync(self, request: Any) -> Any:
        meta = getattr(request, "metadata", None)
        meta = meta if isinstance(meta, dict) else {}
        tenant, user = str(meta.get("tenant_id") or "").strip(), str(meta.get("user_id") or "").strip()
        correlation, task = str(meta.get("correlation_key") or "").strip(), str(meta.get("task_type") or "").strip()
        model = str(getattr(request, "model", "") or "").strip()
        if not all((tenant, user, correlation, task, model)) or not has_durable_budget_store(self._store):
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE")

        supplied = meta.get("request_id")
        if supplied is not None and (
            not isinstance(supplied, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", supplied)
        ):
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE")
        request_id = supplied or "llm-gateway-" + hashlib.sha256(
            "\0".join((tenant, user, correlation, task, model)).encode()
        ).hexdigest()[:32]
        estimate = estimate_request_tokens(request)
        ctx = TelemetryContext(
            tenant_id=tenant, user_id=user, message_id=str(meta.get("message_id") or ""),
            correlation_id=correlation,
        )
        event_meta = {
            key: value for key in _METADATA_KEYS
            if isinstance((value := meta.get(key)), str) and value.strip() and len(value) <= 512
        }
        try:
            day = self._budget.reserve(
                tenant_id=tenant, user_id=user, tokens=estimate, request_id=request_id,
            )
        except Exception as exc:
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE") from exc
        if day is None:
            append_event_sync(
                event_store=self._store, event_type=LLM_BUDGET_BLOCKED, ctx=ctx,
                payload={"request_id": request_id, "provider": self._provider, "model": model,
                         "estimated_tokens": estimate, **event_meta},
            )
            raise RuntimeError("LLM_BUDGET_BLOCKED")

        try:
            append_event_sync(
                event_store=self._store, event_type=LLM_REQUESTED, ctx=ctx, required=True,
                payload={"request_id": request_id, "provider": self._provider, "model": model, **event_meta},
            )
        except Exception as exc:
            if not self._budget.cancel_unstarted_reservation(tenant_id=tenant, request_id=request_id, day=day):
                raise RuntimeError("LLM_ACCOUNTING_RESERVATION_CANCEL_FAILED") from exc
            raise RuntimeError("LLM_ACCOUNTING_REQUEST_WRITE_FAILED") from exc

        started = time.monotonic()
        response = self._provider_call(self._client, request)
        usage_obj = getattr(response, "usage", None)
        usage = validated_llm_usage(usage_obj)
        if usage is None:
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE")
        prompt, completion, total = usage
        categories = tuple(getattr(usage_obj, key, 0) for key in (
            "cached_input_tokens", "cache_write_input_tokens", "reasoning_output_tokens",
        ))
        if any(type(value) is not int or value < 0 for value in categories):
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE")
        cached, cache_write, reasoning = categories
        if cached + cache_write > prompt or reasoning > completion:
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE")
        if self._provider == "anthropic" and (cached or cache_write):
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE")

        raw = getattr(response, "raw", None)
        raw = raw if isinstance(raw, dict) else {}
        provider_model = raw.get("model") if isinstance(raw.get("model"), str) else ""
        provider_id = next((raw.get(key) for key in ("id", "request_id", "requestId")
                            if isinstance(raw.get(key), str)
                            and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", raw[key])), "")
        try:
            append_event_sync(
                event_store=self._store, event_type=LLM_COMPLETED, ctx=ctx, required=True,
                payload={
                    "request_id": request_id, "provider": self._provider, "model": model,
                    "requested_model": model, "provider_model": provider_model,
                    "provider_model_reported": bool(provider_model),
                    "provider_request_id": provider_id, "provider_request_id_reported": bool(provider_id),
                    "prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total,
                    "usage_schema_version": 2, "cached_input_tokens": cached,
                    "cache_write_input_tokens": cache_write, "reasoning_output_tokens": reasoning,
                    "latency_ms": max(0, int((time.monotonic() - started) * 1000)),
                    "finish_reason": str(getattr(response, "finish_reason", "") or ""),
                    "cache_hit": False, "ok": True, "error_code": "", **event_meta,
                },
            )
        except Exception as exc:
            raise RuntimeError("LLM_ACCOUNTING_COMPLETION_WRITE_FAILED") from exc
        if not self._budget.release(tenant_id=tenant, request_id=request_id, day=day):
            raise RuntimeError("LLM_ACCOUNTING_RESERVATION_RELEASE_FAILED")
        return response

    async def generate(self, request: Any) -> Any:
        return await asyncio.to_thread(self.generate_sync, request)
