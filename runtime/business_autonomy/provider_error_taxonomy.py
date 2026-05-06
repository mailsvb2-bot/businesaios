from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

CANON_PROVIDER_ERROR_TAXONOMY = True


@dataclass(frozen=True)
class ProviderRuntimeErrorView:
    provider_key: str
    category: str
    code: str
    retryable: bool
    message: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ProviderErrorTaxonomy:
    def classify(self, *, provider_key: str, error: Exception) -> ProviderRuntimeErrorView:
        message = str(error or '').strip() or error.__class__.__name__
        if isinstance(error, TimeoutError):
            return ProviderRuntimeErrorView(
                provider_key=provider_key,
                category='transport_timeout',
                code='transport_timeout',
                retryable=True,
                message=message,
                metadata={'exception_type': error.__class__.__name__},
            )
        if isinstance(error, PermissionError):
            return ProviderRuntimeErrorView(
                provider_key=provider_key,
                category='authorization',
                code='permission_denied',
                retryable=False,
                message=message,
                metadata={'exception_type': error.__class__.__name__},
            )
        if isinstance(error, ConnectionError):
            return ProviderRuntimeErrorView(
                provider_key=provider_key,
                category='transport_unavailable',
                code='connection_error',
                retryable=True,
                message=message,
                metadata={'exception_type': error.__class__.__name__},
            )
        if isinstance(error, ValueError):
            return ProviderRuntimeErrorView(
                provider_key=provider_key,
                category='invalid_request',
                code='invalid_request',
                retryable=False,
                message=message,
                metadata={'exception_type': error.__class__.__name__},
            )
        return ProviderRuntimeErrorView(
            provider_key=provider_key,
            category='provider_runtime_error',
            code=error.__class__.__name__.lower(),
            retryable=False,
            message=message,
            metadata={'exception_type': error.__class__.__name__},
        )


__all__ = ['CANON_PROVIDER_ERROR_TAXONOMY', 'ProviderErrorTaxonomy', 'ProviderRuntimeErrorView']
