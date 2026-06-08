from __future__ import annotations

from typing import Any

import yaml

from runtime._internal.effects_actions.offer_patch_helpers import append_line, resolve_catalog_path
from runtime.platform.config.yaml_loader import load_yaml
from runtime.tenancy import require_tenant_id


def resolve_offer_catalog(*, tenant_id: str, product: str, env: str) -> tuple[str, Any]:
    tenant = require_tenant_id(tenant_id)
    prod = str(product).strip() or "organization_platform"
    envv = str(env).strip() or "prod"
    _base, cat_path = resolve_catalog_path(tenant_id=tenant, product=prod, env=envv)
    return f"{tenant}:{prod}:{envv}", cat_path


def load_offer_catalog(path: Any) -> dict[str, Any]:
    raw = {}
    if path.exists():
        raw = load_yaml(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def locate_offer(*, offers: list, offer_id: str) -> dict[str, Any]:
    oid = str(offer_id).strip() or "unknown_offer"
    for item in offers:
        if isinstance(item, dict) and str(item.get("offer_id") or "") == oid:
            return item
    target = {
        "offer_id": oid,
        "base_price_rub": 0,
        "rules": {"cooldown_hours": 24},
        "variants": {"a": {"title": "", "body": ""}},
        "meta": {},
    }
    offers.append(target)
    return target


def suggest_patch_for_action(*, target: dict[str, Any], action: str) -> tuple[str, str, dict[str, Any]]:
    effect = str(target.get("effect") or target.get("title") or "заметный результат").strip()
    days = int(target.get("days") or 7)
    act = str(action).strip() or "improve_ctr"

    if act == "improve_ctr":
        return (
            "Усилить 1-ю строку (CTR)",
            "Сильнее конкретика + обещание результата + снижение риска.",
            {"headline": f"За {days} дней: {effect}. Без риска — гарантия."},
        )
    if act == "reduce_friction":
        return (
            "Снизить трение (простота)",
            "Снижаем барьер входа.",
            {"subheadline": "Запишем за 2 минуты. Без предоплаты."},
        )
    if act == "increase_trust":
        return (
            "Усилить доверие",
            "Доверие критично в микробизнесе.",
            {"guarantee_line": "Гарантия результата или вернём деньги."},
        )
    if act == "increase_urgency":
        return (
            "Добавить срочность",
            "Ограничение повышает конверсию.",
            {"urgency_line": "Осталось 3 места на эту неделю."},
        )
    return (f"Подсказка: {act}", "Базовый вариант.", {"headline": f"{effect} — за {days} дней"})


def summarize_patch_application(*, target: dict[str, Any], patch: dict[str, Any]) -> tuple[str, str, bool]:
    before = yaml.safe_dump(target, sort_keys=False, allow_unicode=True)

    variants = target.get("variants") if isinstance(target.get("variants"), dict) else {}
    variant_a = variants.get("a") if isinstance(variants.get("a"), dict) else {}
    title = str(variant_a.get("title") or "")
    body = str(variant_a.get("body") or "")

    if "headline" in patch:
        variant_a["title"] = str(patch.get("headline") or title)
    if "body" in patch:
        variant_a["body"] = str(patch.get("body") or body)
    if "subheadline" in patch:
        variant_a["body"] = append_line(variant_a.get("body") or body, str(patch.get("subheadline") or ""))
    if "guarantee_line" in patch:
        target["guarantee_line"] = str(patch.get("guarantee_line") or "")
    if "urgency_line" in patch:
        target["urgency_line"] = str(patch.get("urgency_line") or "")

    target["variants"] = {**variants, "a": variant_a}
    after = yaml.safe_dump(target, sort_keys=False, allow_unicode=True)
    return before, after, before != after
