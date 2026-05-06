# CANON: Multichannel Runtime Etalon V11

## Non-negotiable rules
- exactly one runtime app bootstrap
- exactly one pipeline
- exactly one delivery dispatcher
- exactly one execution contract
- exactly one canonical data flow
- channel bindings are transport-only
- config shapes runtime mechanics only
- telemetry/audit observe facts only
- delivery/state do not alter business meaning
- DecisionCore remains outside this runtime

## Canonical data flow
inbound raw
-> parse
-> MessageEnvelope
-> RouteCommand
-> canonical worldstate builder
-> compose view
-> view resolver
-> OutboundEnvelope
-> outbound queue
-> delivery dispatcher
-> provider ack reconciliation
-> telemetry/audit

## Forbidden
- hidden business logic in parsing/routing/bindings
- provider-specific second brains
- parallel bootstraps
- alternative pipelines
- fake success transport stubs presented as production-ready
