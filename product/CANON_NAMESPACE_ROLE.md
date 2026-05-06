# product namespace role

This package is the **runtime-facing product service surface**.

Allowed here:
- product experience services
- activation/onboarding/value realization flows
- notification and copy helpers
- thin product-facing facades over canonical lower layers

Must NOT contain:
- product catalog manifests
- product YAML contract loading
- operator catalog resolution
- static pricing/telemetry schema registries
- a second product-definition truth beside `products/`

Rule:
- `product/` is for **service behavior and experience orchestration**.
- `products/` is for **catalogs, contracts, loaders, manifests, and packaged definitions**.
