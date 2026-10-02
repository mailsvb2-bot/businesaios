from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import time
from typing import Any, Protocol

from core.llm.agent.contracts import LLMTaskContext, LLMTaskResult
from core.llm.agent.parse import extract_json_block
from core.llm.agent.prompts import (
    build_context_bundle,
    build_system_prompt,
    build_user_prompt,
    prompt_versions_for,
)
from core.llm.agent.tasks import TaskType
from core.llm.contracts import LLMMessage, LLMRequest


class LLMGatewayLike(Protocol):
    def generate_sync(self, req: LLMRequest): ...


@dataclass(frozen=True)
class LLMAgentConfig:
    default_model: str
    temperature: float = 0.4
    max_tokens: int = 700
    timeout_s: float = 25.0
    context_token_budget: int = 4_000
    context_privacy_budget: tuple[str, ...] = ("public", "internal", "confidential")
    context_max_age_seconds: float | None = None
    model_profile_id: str | None = None
    pinned_model_profile_id: str | None = None


def _invoke_gateway(gateway: LLMGatewayLike, req: LLMRequest):
    return gateway.generate_sync(req)


class LLMAgent:
    def __init__(
        self,
        gateway: LLMGatewayLike,
        cfg: LLMAgentConfig,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._gateway = gateway
        self._cfg = cfg
        self._clock = clock or time

    def run_task(
        self,
        task: TaskType,
        ctx: LLMTaskContext,
        *,
        model: str | None = None,
    ) -> LLMTaskResult:
        system_prompt_version, task_prompt_version = prompt_versions_for(task)
        context_bundle = build_context_bundle(
            task,
            ctx,
            token_budget=self._cfg.context_token_budget,
            privacy_budget=frozenset(self._cfg.context_privacy_budget),
            max_age_seconds=self._cfg.context_max_age_seconds,
            now_s=self._clock() if self._cfg.context_max_age_seconds is not None else None,
        )
        sys = build_system_prompt(task, ctx.locale)
        user = build_user_prompt(task, ctx, context_bundle=context_bundle)

        metadata: dict[str, Any] = {
            "task_type": str(task.value),
            "tenant_id": ctx.tenant_id,
            "product_id": ctx.product_id,
            "user_id": ctx.user_id,
            "correlation_key": ctx.correlation_key,
            "context_tokens": context_bundle.estimated_tokens,
            "context_provenance": context_bundle.provenance(),
            "required_model_capabilities": ("structured_output",),
            "system_prompt_version": system_prompt_version,
            "task_prompt_version": task_prompt_version,
        }
        if self._cfg.model_profile_id:
            metadata["preferred_model_profile_id"] = self._cfg.model_profile_id
        if self._cfg.pinned_model_profile_id:
            metadata["pinned_model_profile_id"] = self._cfg.pinned_model_profile_id

        req = LLMRequest(
            model=model or self._cfg.default_model,
            messages=[
                LLMMessage(role="system", content=sys),
                LLMMessage(role="user", content=user),
            ],
            temperature=self._cfg.temperature,
            max_tokens=self._cfg.max_tokens,
            timeout_s=self._cfg.timeout_s,
            metadata=metadata,
            model_profile_id=self._cfg.model_profile_id,
            prompt_versions={
                "system": system_prompt_version,
                "task": task_prompt_version,
            },
        )

        resp = _invoke_gateway(self._gateway, req)
        raw_text = getattr(resp, "content", "") or ""
        json_data, rest_text = extract_json_block(raw_text)

        meta: dict[str, Any] = {
            "finish_reason": getattr(resp, "finish_reason", None),
            "usage": getattr(resp, "usage", None),
            "model": req.model,
            "model_profile_id": req.model_profile_id,
            "task_type": task.value,
            "prompt_versions": dict(req.prompt_versions or {}),
            "context_tokens": context_bundle.estimated_tokens,
            "context_provenance": context_bundle.provenance(),
        }
        return LLMTaskResult(
            text=(rest_text or raw_text).strip(),
            json=json_data,
            meta=meta,
        )
