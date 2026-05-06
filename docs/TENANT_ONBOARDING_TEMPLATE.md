# BusinesAIOS tenant onboarding template

This repository is prepared for many organizations on one platform.

## Add a new organization
1. Copy `products/organization_platform.yaml` to `products/<tenant_or_domain>.yaml`.
2. Add tenant-specific offer catalog in `products/offer_catalogs/` and `data/offer_catalogs/<tenant>/<product>/`.
3. Add operator tuning in `products/operator_catalogs/`.
4. Keep DecisionCore, payments, telemetry and ads connectors in shared platform layers.
5. Do not fork business logic into hidden tenant-only code paths; use contracts and catalogs.
