from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class OfferCatalog(Protocol):
    def get_offer(self, *, tenant_id: str, offer_id: str) -> dict: ...
    def upsert_offer(self, *, tenant_id: str, offer: dict) -> None: ...


@dataclass(frozen=True)
class OfferSuggestion:
    offer_id: str
    title: str
    patch: dict
    reason: str


@dataclass
class OfferSuggester:
    """Non-LLM offer diff suggestions (safe fields only)."""

    catalog: OfferCatalog

    def suggest(self, *, tenant_id: str, offer_id: str, action: str) -> OfferSuggestion:
        offer = self.catalog.get_offer(tenant_id=tenant_id, offer_id=offer_id)
        headline = (offer.get("headline") or "").strip()
        effect = (offer.get("effect") or "заметный результат").strip()
        days = int(offer.get("days") or 7)

        patch: dict = {}
        reason = ""
        title = ""

        if action == "improve_ctr":
            title = "Усилить 1-ю строку (CTR)"
            patch["headline"] = f"За {days} дней: {effect}. Без риска — гарантия."
            patch["subheadline"] = "Сразу увидишь формат и первые изменения."
            reason = "CTR низкий — усиливаем первый экран: конкретика + срок + риск↓"
        elif action == "improve_cr":
            title = "Снизить риск (CR)"
            patch["guarantee_line"] = "Гарантия 7 дней: не почувствуешь эффект — верну деньги."
            patch["urgency_line"] = "Цена действует до завтра."
            reason = "CR низкий — добавляем гарантию/срок, чтобы снять барьер оплаты"
        elif action == "double_winner":
            title = "Удвоить победителя (scale)"
            patch["urgency_line"] = patch.get("urgency_line") or "Сегодня — лучший момент начать."
            reason = "Метрики норм — масштабируем победителя, добавляя мягкую срочность"
        else:
            title = "Повысить показы (coverage)"
            patch["distribution_hint"] = {"extra_slot_per_day": 1}
            reason = "Слишком мало показов — добавляем частоту/триггеры"

        if not headline and "headline" not in patch:
            patch["headline"] = f"За {days} дней: {effect}. Попробуй без риска."

        return OfferSuggestion(offer_id=str(offer_id), title=title, patch=patch, reason=reason)
