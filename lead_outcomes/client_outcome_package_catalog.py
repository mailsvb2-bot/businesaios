from __future__ import annotations

from dataclasses import dataclass

from lead_outcomes.client_outcome_contract import ClientOutcomePackage

CANON_CLIENT_OUTCOME_PACKAGE_CATALOG = True


@dataclass(frozen=True, slots=True)
class ClientOutcomePackageCatalog:
    packages: tuple[ClientOutcomePackage, ...]

    @classmethod
    def default_catalog(cls) -> 'ClientOutcomePackageCatalog':
        return cls(
            packages=(
                ClientOutcomePackage('clients-1', '1 client', 1, 85.0, trust_tier='tier0_manual'),
                ClientOutcomePackage('clients-5', '5 clients', 5, 70.0, trust_tier='tier1_crm'),
                ClientOutcomePackage('clients-10', '10 clients', 10, 60.0, trust_tier='tier1_crm'),
                ClientOutcomePackage('clients-25', '25 clients', 25, 52.0, attribution_window_days=45, trust_tier='tier2_crm_payments'),
            )
        )

    def list_packages(self) -> tuple[ClientOutcomePackage, ...]:
        return tuple(item.normalized_copy() for item in self.packages)

    def get_by_id(self, package_id: str) -> ClientOutcomePackage:
        normalized = str(package_id or '').strip()
        for package in self.packages:
            if package.package_id == normalized:
                return package.normalized_copy()
        raise KeyError(normalized)

    def get_by_requested_clients(self, requested_clients: int) -> ClientOutcomePackage:
        requested = max(1, int(requested_clients))
        for package in self.packages:
            if package.requested_clients == requested:
                return package.normalized_copy()
        raise KeyError(str(requested))
