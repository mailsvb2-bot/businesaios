from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from core.llm.budget import (
    BudgetCaps,
    EventStoreDailyTokenBudget,
    estimate_request_tokens,
    has_durable_budget_store,
    validated_llm_usage,
)
from core.marketing.llm_telemetry import append_event_sync
from core.telemetry.event_types import LLM_BUDGET_BLOCKED, LLM_COMPLETED, LLM_REQUESTED
from core.telemetry.event_writer import TelemetryContext


_AUDIT_METADATA_KEYS = (
    "task_type",
    "prompt_version",
    "prompt_hash",
    "experiment",
    "variant",
    "offer_id",
    "model_profile_id",
    "model_version",
    "model_policy_id",
    "model_policy_version",
    "model_fallback_from_profile_id",
)


def _safe_audit_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    result: dict[str, str | int | float | bool] = {}
    for key in _AUDIT_METADATA_KEYS:
        value = metadata.get(key)
        if isinstance(value, str):
            if value.strip():
                result[key] = value.strip()[:160]
        elif type(value) in {int, float, bool}:
            result[key] = value
    return result


class AccountedSyncGateway:
    """Single durable provider boundary for every real LLM execution surface."""

    def __init__(
        self,
        client: Any,
        *,
        event_store: Any,
        provider: str,
        budget: EventStoreDailyTokenBudget | None = None,
    ) -> None:
        if not has_durable_budget_store(event_store):
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE")
        self._client = client
        self._store = event_store
        self._provider = str(provider)
        self._budget = budget or EventStoreDailyTokenBudget(
            event_store=event_store,
            caps=BudgetCaps(),
        )

    @property
    def budget(self) -> EventStoreDailyTokenBudget:
        """The same canonical budget instance used by this provider gateway."""
        return self._budget

    def _generate_provider(self, request: Any) -> Any:
        generate_sync = getattr(self._client, "generate_sync", None)
        if callable(generate_sync):
            return generate_sync(request)
        generate_async = getattr(self._client, "generate", None)
        if not callable(generate_async):
            raise RuntimeError("LLM_PROVIDER_GENERATE_UNAVAILABLE")
        from core.marketing.async_runner import run_awaitable_sync

        return run_awaitable_sync(generate_async(request))

    def generate_sync(self, request: Any) -> Any:
        metadata = dict(request.metadata or {})
        tenant = str(metadata.get("tenant_id") or "").strip()
        user = str(metadata.get("user_id") or "").strip()
        correlation = str(metadata.get("correlation_key") or "").strip()
        task = str(metadata.get("task_type") or "").strip()
        if not all((tenant, user, correlation, task)):
            raise RuntimeError("LLM_ACCOUNTING_UNAVAILABLE")

        identity = hashlib.sha256(
            "\0".join((tenant, user, correlation, task, str(request.model))).encode("utf-8")
        ).hexdigest()[:32]
        request_id = f"llm-gateway-{identity}"
        estimated_tokens = estimate_request_tokens(request)
        day = self._budget.reserve(
            tenant_id=tenant,
            user_id=user,
            tokens=estimated_tokens,
            request_id=request_id,
        )
        ctx = TelemetryContext(
            tenant_id=tenant,
            user_id=user,
            message_id=correlation,
            correlation_id=correlation,
        )
        audit = _safe_audit_metadata(metadata)
        if day is None:
            try:
                append_event_sync(
                    event_store=self._store,
                    event_type=LLM_BUDGET_BLOCKED,
                    ctx=ctx,
                    required=True,
                    payload={
                        "request_id": request_id,
                        "provider": self._provider,
                        "model": str(request.model),
                        "estimated_tokens": estimated_tokens,
                        **audit,
                    },
                )
            except Exception as exc:
                raise RuntimeError("LLM_ACCOUNTING_BUDGET_EVENT_UNAVAILABLE") from exc
            raise RuntimeError("LLM_BUDGET_BLOCKED")

        try:
            append_event_sync(
                event_store=self._store,
                event_type=LLM_REQUESTED,
                ctx=ctx,
                required=True,
                payload={
                    "request_id": request_id,
                    "provider": self._provider,
                    "model": str(request.model),
                    "estimated_tokens": estimated_tokens,
                    **audit,
                },
            )
        except Exception as exc:
            self._budget.cancel_unstarted_reservation(
                tenant_id=tenant,
                request_id=request_id,
                day=day,
            )
            raise RuntimeError("LLM_ACCOUNTING_REQUEST_UNAVAILABLE") from exc

        # A provider exception or unverifiable usage deliberately retains the
        # reservation: the remote provider may already have charged the call.
        response = self._generate_provider(request)
        usage = validated_llm_usage(getattr(response, "usage", None))
        if usage is None:
            raise RuntimeError("LLM_ACCOUNTING_USAGE_UNAVAILABLE")
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
                    "model": str(request.model),
                    "prompt_tokens": prompt,
                    "completion_tokens": completion,
                    "total_tokens": total,
                    "finish_reason": str(getattr(response, "finish_reason", "") or ""),
                    **audit,
                },
            )
        except Exception as exc:
            raise RuntimeError("LLM_ACCOUNTING_COMPLETION_UNAVAILABLE") from exc
        if not self._budget.release(tenant_id=tenant, request_id=request_id, day=day):
            raise RuntimeError("LLM_ACCOUNTING_RELEASE_UNAVAILABLE")
        return response

    async def generate(self, request: Any) -> Any:
        """Async callers use the same accounted provider path, never a raw bypass."""
        return await asyncio.to_thread(self.generate_sync, request)
