# observability.platform.telemetry namespace role

Canonical role:
- owner of append-only platform telemetry event primitives
- owner of metric-event emission helpers and event-stream sinks

Allowed:
- append-only telemetry store contracts
- metric event emission
- in-memory/platform-safe event stream helpers

Forbidden:
- business policy logic
- routing or decision semantics
- re-defining duplicate telemetry store/sink owners in sibling modules
