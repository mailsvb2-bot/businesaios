from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Mapping


class RegionChoice(str, Enum):
    """User-provided region hint for launch planning.

    Keep it UX-friendly: "city/country" free-text is allowed in Diagnostics.region.
    This enum is for coarse presets in UI (optional).
    """

    UNKNOWN = "unknown"
    LOCAL = "local"
    COUNTRY = "country"
    WORLD = "world"


class HasClientsChoice(str, Enum):
    YES = "yes"
    NO = "no"
    SOME = "some"
    UNKNOWN = "unknown"


class BudgetChoice(str, Enum):
    """Budget presets for 7d sprint (minor units)."""

    EUR_300 = "eur_300"
    EUR_500 = "eur_500"
    EUR_1000 = "eur_1000"


def budget_choice_to_minor(choice: BudgetChoice) -> tuple[int, str]:
    if choice == BudgetChoice.EUR_300:
        return 300_00, "EUR"
    if choice == BudgetChoice.EUR_500:
        return 500_00, "EUR"
    if choice == BudgetChoice.EUR_1000:
        return 1000_00, "EUR"
    return 0, "EUR"


@dataclass(frozen=True)
class Diagnostics:
    """Onboarding answers (minimal, product-facing)."""

    what: str = ""
    avg_check_minor: int = 0
    currency: str = "RUB"
    margin_pct: int = 0
    region: str = ""
    has_clients: HasClientsChoice = HasClientsChoice.UNKNOWN

    # 7d test budget (minor units) for external traffic.
    budget_minor_7d: int = 0
    budget_currency: str = "EUR"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "what": self.what,
            "avg_check_minor": int(self.avg_check_minor or 0),
            "currency": self.currency,
            "margin_pct": int(self.margin_pct or 0),
            "region": self.region,
            "has_clients": str(self.has_clients.value),
            "budget_minor_7d": int(self.budget_minor_7d or 0),
            "budget_currency": self.budget_currency,
        }

    @staticmethod
    def from_dict(d: Mapping[str, Any] | None) -> "Diagnostics":
        d = dict(d or {})
        try:
            hc = HasClientsChoice(str(d.get("has_clients") or HasClientsChoice.UNKNOWN.value))
        except Exception:
            hc = HasClientsChoice.UNKNOWN
        return Diagnostics(
            what=str(d.get("what") or "")[:200],
            avg_check_minor=int(d.get("avg_check_minor") or 0),
            currency=str(d.get("currency") or "RUB")[:8],
            margin_pct=int(d.get("margin_pct") or 0),
            region=str(d.get("region") or "")[:64],
            has_clients=hc,
            budget_minor_7d=int(d.get("budget_minor_7d") or 0),
            budget_currency=str(d.get("budget_currency") or "EUR")[:8],
        )


def parse_int_from_text(text: str) -> int:
    t = str(text or "")
    digits = "".join(ch for ch in t if ch.isdigit())
    try:
        return int(digits or "0")
    except Exception:
        return 0


def rub_to_minor(rub_amount: int) -> int:
    return int(rub_amount or 0) * 100
