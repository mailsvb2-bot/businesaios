from __future__ import annotations


class FinanceError(Exception):
    """Base for finance domain errors. Canon: core/finance only; no side-effects."""

    def __init__(self, msg: str = "") -> None:
        super().__init__(msg or self.__class__.__name__)


class FinanceValidationError(FinanceError):
    pass


class NegativeCashflowViolation(FinanceError):
    pass


class PayoutRiskViolation(FinanceError):
    pass


class LiquidityViolation(FinanceError):
    pass


class FinanceGuardViolation(FinanceError):
    pass
