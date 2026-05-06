# CANON: Messaging Policy

## Role

Messaging policy is an execution-ordering and observability layer for already-issued decisions.
It is not a decision brain.

## Hard rules

- Messaging policy must never issue business decisions.
- Messaging policy must never override DecisionCore.
- Messaging policy must never create a second event store.
- Messaging policy snapshots, traces, dashboards, alerts and subscriptions are read/observability layers only.
- Alert notifications are observability notifications only and must not trigger remediation actions.
- Multichannel dispatch must stay transport-level and must not hide business rules.
- Tenant scoping is mandatory for settings and event-store reads.
- Alert notification dedup is allowed only as a delivery-noise guard, not as a business filter.

## Execution contract

Canonical path:

DecisionCore -> RuntimeExecutor -> messaging policy execution -> event log -> read model -> dashboard/alerts/subscriptions

Forbidden:

- direct LLM ranking inside messaging policy execution
- hidden policy override flags in transport payload
- alternative alert-driven business actions
- direct ads apply from autopilot tick
