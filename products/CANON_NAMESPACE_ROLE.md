# products namespace role

This package is the **product-definition and catalog surface**.

Allowed here:
- product contracts
- product loaders/resolvers
- offer catalogs
- pricing models
- telemetry schemas
- packaged product definitions and manifests

Must NOT contain:
- runtime activation/orchestration services
- customer communication flows
- magic-moment publishing behavior
- value-realization service logic
- a second business-service layer beside `product/`

Rule:
- `products/` is the canonical home for **definitions and packaged product metadata**.
- `product/` remains the home for **runtime-facing product services**.
