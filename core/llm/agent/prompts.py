from __future__ import annotations

import json
from typing import Any

from core.llm.agent.contracts import LLMTaskContext
from core.llm.agent.tasks import TaskType
from core.llm.context import (
    ContextBudget,
    ContextBuilder,
    ContextBundle,
    ContextFact,
    ContextRequirement,
    ContextSource,
)

SYSTEM_PROMPT_VERSION = "growth.system.v1"
TASK_PROMPT_VERSIONS = {task: f"{task.value}.v1" for task in TaskType}

_TASK_CONTEXT_FIELDS: dict[TaskType, tuple[str, ...]] = {
    TaskType.ADS_CREATIVE_GENERATE: ("business", "offer", "audience", "campaign", "constraints"),
    TaskType.ADS_CREATIVE_CRITIQUE: ("business", "offer", "audience", "campaign", "constraints"),
    TaskType.ADS_PLAN_BUILD: ("business", "offer", "audience", "campaign", "metrics", "constraints"),
    TaskType.ADS_ANALYTICS_SUMMARY: ("business", "campaign", "metrics", "constraints"),
    TaskType.OFFER_GENERATE: ("business", "offer", "audience", "constraints"),
    TaskType.OFFER_RISK_REDUCE: ("business", "offer", "audience", "constraints"),
    TaskType.PRICING_SUGGEST: ("business", "offer", "audience", "metrics", "constraints"),
    TaskType.LANDING_COPY_GENERATE: ("business", "offer", "audience", "constraints"),
    TaskType.LANDING_COPY_IMPROVE: ("business", "offer", "audience", "constraints"),
}


def prompt_versions_for(task: TaskType) -> tuple[str, str]:
    return SYSTEM_PROMPT_VERSION, TASK_PROMPT_VERSIONS[task]


def _context_fact(ctx: LLMTaskContext, key: str, value: Any) -> ContextFact:
    evidence_raw = ctx.context_evidence_ids.get(key, ())
    if isinstance(evidence_raw, str):
        evidence_ids = (evidence_raw,) if evidence_raw else ()
    else:
        evidence_ids = tuple(str(item) for item in (evidence_raw or ()) if str(item))
    observed_raw = ctx.context_observed_at.get(key)
    observed_at = float(observed_raw) if observed_raw is not None else None
    return ContextFact(
        key=key,
        value=value,
        source=str(ctx.context_provenance.get(key) or "task_context"),
        evidence_ids=evidence_ids,
        observed_at=observed_at,
        privacy_class=str(ctx.context_privacy_classes.get(key) or "internal"),
    )


def build_context_bundle(
    task: TaskType,
    ctx: LLMTaskContext,
    *,
    token_budget: int = 4_000,
    privacy_budget: frozenset[str] | None = None,
) -> ContextBundle:
    fields = _TASK_CONTEXT_FIELDS[task]
    world_model: dict[str, ContextFact] = {}
    constraints: dict[str, ContextFact] = {}
    requirements: list[ContextRequirement] = []

    for key in fields:
        value = getattr(ctx, key)
        if not value:
            continue
        fact = _context_fact(ctx, key, value)
        source = ContextSource.CONSTRAINT if key == "constraints" else ContextSource.WORLD_MODEL
        target = constraints if source is ContextSource.CONSTRAINT else world_model
        target[key] = fact
        requirements.append(ContextRequirement(source=source, key=key))

    return ContextBuilder().build(
        task=task.value,
        requirements=requirements,
        world_model=world_model,
        constraints=constraints,
        budget=ContextBudget(
            token_budget=token_budget,
            privacy_budget=privacy_budget
            or frozenset({"public", "internal", "confidential"}),
        ),
    )


def build_system_prompt(task: TaskType, locale: str) -> str:
    _ = task
    base = {
        "ru": (
            "Ты — помощник по маркетингу и росту. "
            "Дай результат строго по задаче. "
            "Если нужен JSON — верни JSON в начале ответа в блоке ```json```.\n"
            "Запрещено: выдумывать факты/цифры без входных данных. "
            "Если данных не хватает — явно перечисли, что нужно.\n"
        ),
        "en": (
            "You are a growth/marketing assistant. "
            "Answer strictly per task. "
            "If JSON is needed, output JSON first in a ```json``` block.\n"
            "Never fabricate facts or numbers not provided. "
            "If data is missing, list what you need.\n"
        ),
    }
    return base.get(locale, base["ru"])


def build_user_prompt(
    task: TaskType,
    ctx: LLMTaskContext,
    *,
    context_bundle: ContextBundle | None = None,
) -> str:
    payload = (
        context_bundle
        or build_context_bundle(task, ctx)
    ).as_payload()

    if task == TaskType.ADS_CREATIVE_GENERATE:
        return (
            "Сгенерируй 5 вариантов рекламного креатива.\n"
            "Формат JSON:\n"
            "{ creatives: [ {title, text, cta, angle, risk_reduction, hypothesis, target_segment}... ] }\n"
            "Дальше кратко объясни логику.\n\n"
            f"INPUT:\n{json.dumps(payload, ensure_ascii=False)}"
        )
    if task == TaskType.ADS_CREATIVE_CRITIQUE:
        return (
            "Оцени креатив(ы), найди слабые места и предложи улучшения.\n"
            "Формат JSON:\n"
            "{ critique: [ {issue, why, fix}... ], score_0_100, best_angle }\n\n"
            f"INPUT:\n{json.dumps(payload, ensure_ascii=False)}"
        )
    if task == TaskType.ADS_PLAN_BUILD:
        return (
            "Собери план запуска/оптимизации рекламы на 7 дней.\n"
            "Формат JSON:\n"
            "{ plan: [ {day, actions:[...], budget, kpi, guardrails:[...]}... ] }\n\n"
            f"INPUT:\n{json.dumps(payload, ensure_ascii=False)}"
        )
    if task == TaskType.ADS_ANALYTICS_SUMMARY:
        return (
            "Сделай аналитическую сводку по метрикам: что работает/не работает и что делать дальше.\n"
            "Формат JSON:\n"
            "{ summary, problems:[...], next_actions:[...], experiments:[...] }\n\n"
            f"INPUT:\n{json.dumps(payload, ensure_ascii=False)}"
        )
    if task == TaskType.OFFER_GENERATE:
        return (
            "Сгенерируй 3 оффера. Каждый: продукт/результат/механика/условия/гарантии/CTA.\n"
            "Формат JSON:\n"
            "{ offers: [ {name, promise, mechanism, terms, guarantees, cta, objections_handled:[...]}... ] }\n\n"
            f"INPUT:\n{json.dumps(payload, ensure_ascii=False)}"
        )
    if task == TaskType.OFFER_RISK_REDUCE:
        return (
            "Снизь риск для покупателя: добавь гарантию/доказательства/обратимость/триал.\n"
            "Формат JSON:\n"
            "{ risk_reduction: [ {idea, why, implementation}... ] }\n\n"
            f"INPUT:\n{json.dumps(payload, ensure_ascii=False)}"
        )
    if task == TaskType.PRICING_SUGGEST:
        return (
            "Предложи цены и упаковку (3 тарифа). Учитывай платежеспособность и снижение риска.\n"
            "Формат JSON:\n"
            "{ tiers:[ {name, price, value, constraints, target_segment}... ], notes }\n\n"
            f"INPUT:\n{json.dumps(payload, ensure_ascii=False)}"
        )
    if task == TaskType.LANDING_COPY_GENERATE:
        return (
            "Сгенерируй структуру лендинга (hero, proof, mechanism, FAQ, CTA) + тексты.\n"
            "Формат JSON:\n"
            "{ sections:[ {id,title,copy}... ], seo:{title,description} }\n\n"
            f"INPUT:\n{json.dumps(payload, ensure_ascii=False)}"
        )
    if task == TaskType.LANDING_COPY_IMPROVE:
        return (
            "Улучшай текст лендинга: ясность, конкретика, доказательства, снижение риска.\n"
            "Формат JSON:\n"
            "{ improved_sections:[ {id,before,after,why}... ] }\n\n"
            f"INPUT:\n{json.dumps(payload, ensure_ascii=False)}"
        )

    return f"INPUT:\n{json.dumps(payload, ensure_ascii=False)}"


__all__ = [
    "SYSTEM_PROMPT_VERSION",
    "TASK_PROMPT_VERSIONS",
    "build_context_bundle",
    "build_system_prompt",
    "build_user_prompt",
    "prompt_versions_for",
]
