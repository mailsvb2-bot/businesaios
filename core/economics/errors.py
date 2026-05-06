from __future__ import annotations


class EconomicsError(Exception):
    """Base economics error."""


class EconomicsConfigurationError(EconomicsError):
    """Raised when economics dependencies or settings are invalid."""


class EconomicsDataError(EconomicsError):
    """Raised when required economics inputs are missing or malformed."""


class EconomicsGuardViolation(EconomicsError):
    """Raised when a blocking economics guard is triggered."""


class EconomicsRepositoryError(EconomicsError):
    """Raised when economics snapshot persistence fails."""
