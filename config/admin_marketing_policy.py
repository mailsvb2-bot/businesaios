from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AdminPricingPolicy:
    min_discount_floor_pct: float = 0.05
    max_discount_floor_pct: float = 0.30
    min_price_major_units: int = 100


@dataclass(frozen=True)
class AdminCopyPolicy:
    default_product_name: str = "BusinesAIOS Workspace"
    fallback_templates: tuple[str, ...] = (
        "{product}: переобучение нервной системы через ритм повседневности.",
        "В дороге можно сделать день мягче. Открой {product}.",
    )
    step_templates: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "nudge": (
                "Как ты сейчас? Открой {product} — короткая сессия поможет выровнять день.",
                "Напоминание: открой {product}, когда удобно. Несколько минут — и ты в ритме.",
            ),
            "post_launch": (
                "Если понравилось — полный доступ откроет утро/вечер под твой ритм. Нажми «Полный доступ».",
                "Пробный доступ — только вход. В полном доступе контент подстраивается под неделю. Один клик.",
            ),
            "offer": (
                "Хочешь закрепить эффект? Полный доступ в один клик — и поехали.",
                "Готов сделать это привычкой? Открой полный доступ — будет мягко и без «занятий собой».",
            ),
            "offer_nextday": (
                "Завтра будет проще, если сегодня настроить ритм. Полный доступ — в один клик.",
                "Если хочешь, чтобы завтра началось ровно — включи полный доступ сейчас.",
            ),
            "deadline": (
                "Напоминание: условия на полный доступ скоро обновятся. Если планировал — сейчас удобный момент.",
                "Скоро закроем текущие условия. Если хочешь — активируй полный доступ сейчас.",
            ),
            "lastcall": (
                "Последний пинг: если хотел полный доступ — лучше нажать сейчас (занимает секунду).",
                "Последний шанс на текущие условия. Один клик — и доступ активен.",
            ),
        }
    )


@dataclass(frozen=True)
class AdminMarketingPolicy:
    pricing: AdminPricingPolicy = field(default_factory=AdminPricingPolicy)
    copy: AdminCopyPolicy = field(default_factory=AdminCopyPolicy)


DEFAULT_ADMIN_MARKETING_POLICY = AdminMarketingPolicy()
