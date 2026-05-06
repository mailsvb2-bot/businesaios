# shared namespace role

Canonical role:
- single owner of reusable cross-domain registry primitives and low-level shared helpers

Allowed:
- generic registry primitives
- shared storage contracts reused by multiple domains

Forbidden:
- domain-specific policy decisions
- connector/runtime orchestration
- duplicate wrapper registries with their own storage semantics unless strictly required for compatibility
