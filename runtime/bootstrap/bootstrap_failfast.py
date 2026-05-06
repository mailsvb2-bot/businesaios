from __future__ import annotations

from runtime.bootstrap.bootstrap_contract import BootstrapFailureCode


class BootstrapError(RuntimeError):
    """Base bootstrap failure."""


class BootstrapLockError(BootstrapError):
    """Raised when canonical bootstrap locks are violated."""


class BootstrapValidationError(BootstrapError):
    """Raised when bootstrap validation fails."""


class BootstrapCompositionError(BootstrapError):
    """Raised when bootstrap composition is inconsistent."""


class BootstrapAttestationError(BootstrapError):
    """Raised when bootstrap attestation fails."""


def format_failfast(code: str, message: str, **details: object) -> str:
    payload = ", ".join(f"{key}={value!r}" for key, value in sorted(details.items()))
    suffix = f" [{payload}]" if payload else ""
    return f"{code}: {message}{suffix}"


def raise_failfast(code: str | BootstrapFailureCode, message: str, **details: object) -> None:
    normalized = code.value if isinstance(code, BootstrapFailureCode) else str(code)
    raise BootstrapValidationError(format_failfast(normalized, message, **details))
