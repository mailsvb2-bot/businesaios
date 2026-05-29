from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from core.llm.agent.contracts import LLMTaskContext, LLMTaskResult
from core.llm.agent.parse import extract_json_block
from core.llm.agent.prompts import build_system_prompt, build_user_prompt
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


def _invoke_gateway(gateway: LLMGatewayLike, req: LLMRequest):
    return gateway.generate_sync(req)


class LLMAgent:
    def __init__(self, gateway: LLMGatewayLike, cfg: LLMAgentConfig) -> None:
        self._gateway = gateway
        self._cfg = cfg

    def run_task(self, task: TaskType, ctx: LLMTaskContext, *, model: str | None = None) -> LLMTaskResult:
        sys = build_system_prompt(task, ctx.locale)
        user = build_user_prompt(task, ctx)

        req = LLMRequest(
            model=model or self._cfg.default_model,
            messages=[
                LLMMessage(role="system", content=sys),
                LLMMessage(role="user", content=user),
            ],
            temperature=self._cfg.temperature,
            max_tokens=self._cfg.max_tokens,
            timeout_s=self._cfg.timeout_s,
            metadata={
                "task_type": str(task.value),
                "tenant_id": ctx.tenant_id,
                "product_id": ctx.product_id,
                "user_id": ctx.user_id,
                "correlation_key": ctx.correlation_key,
            },
        )

        resp = _invoke_gateway(self._gateway, req)
        raw_text = getattr(resp, "content", "") or ""
        json_data, rest_text = extract_json_block(raw_text)

        meta: dict[str, Any] = {
            "finish_reason": getattr(resp, "finish_reason", None),
            "usage": getattr(resp, "usage", None),
            "model": req.model,
            "task_type": task.value,
        }
        return LLMTaskResult(text=(rest_text or raw_text).strip(), json=json_data, meta=meta)
