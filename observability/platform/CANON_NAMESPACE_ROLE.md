# observability.platform canonical role

Allowed:
- platform-level observability facades and reusable telemetry/logging helpers
- storage/export-adjacent observability helpers and package-level public surfaces
- append-only telemetry/event primitives
- public import surfaces for platform-owned observability utilities

Forbidden:
- decision policy truth
- routing/business logic
- second logging owners outside the canonical platform observability surface
