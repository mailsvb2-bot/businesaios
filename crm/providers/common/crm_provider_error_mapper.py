from __future__ import annotations

from crm.crm_error_contract import CrmDomainError


class CrmProviderErrorMapper:
    def map(self, exc: Exception) -> CrmDomainError:
        return CrmDomainError(code='crm_provider_error', message=str(exc), retryable=False)
