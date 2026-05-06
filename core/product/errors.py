from __future__ import annotations


class ProductError(Exception):
    pass


class MissingProductDataError(ProductError):
    pass


class ProductValidationError(ProductError):
    pass


class ProductGuardViolation(ProductError):
    pass
