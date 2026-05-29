from __future__ import annotations

import json
from typing import Any, Dict

from core.llm.agent.contracts import LLMTaskContext
from core.llm.agent.tasks import TaskType


def build_system_prompt(task: TaskType, locale: str) -> str:
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


def build_user_prompt(task: TaskType, ctx: LLMTaskContext) -> str:
    payload: dict[str, Any] = {
        "tenant_id": ctx.tenant_id,
        "user_id": ctx.user_id,
        "product_id": ctx.product_id,
        "business": ctx.business,
        "offer": ctx.offer,
        "audience": ctx.audience,
        "campaign": ctx.campaign,
        "metrics": ctx.metrics,
        "constraints": ctx.constraints,
    }

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
