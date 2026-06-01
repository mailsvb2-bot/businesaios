from __future__ import annotations

from typing import Any


def compose_fallback_message(offer: dict[str, Any], locale: str = "ru") -> str:
    title = offer.get("title") or "подходящий сеанс"
    price = offer.get("price")
    cur = offer.get("currency") or "₽"
    what = offer.get("what_user_gets") or ""

    if str(locale or "ru").startswith("ru"):
        if price:
            base = f"Хочешь продолжить? Я могу предложить «{title}» за {price}{cur}."
            if what:
                base += f" Это: {what}."
            base += " Если ок — нажми «Открыть»."
            return base
        return f"Хочешь продолжить? Предлагаю «{title}». Нажми «Открыть»."

    if price:
        base = f"Want to continue? I can offer “{title}” for {price}{cur}."
        if what:
            base += f" You get: {what}."
        base += " Tap “Open” if ok."
        return base
    return f"Want to continue? Try “{title}”. Tap “Open”."
