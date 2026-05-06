from __future__ import annotations

from core.finance.strategic.input.financial_input_normalizer import FinancialInputNormalizer
from core.finance.strategic.input.financial_input_validator import FinancialInputValidator
from core.finance.strategic.types import FinancialInput


class FinancialInputBuilder:
    def __init__(self, normalizer: FinancialInputNormalizer | None = None, validator: FinancialInputValidator | None = None) -> None:
        self._normalizer = normalizer or FinancialInputNormalizer()
        self._validator = validator or FinancialInputValidator()

    def build(self, raw: dict) -> FinancialInput:
        data = self._normalizer.normalize(raw)
        self._validator.validate(data)
        return FinancialInput(**data)
