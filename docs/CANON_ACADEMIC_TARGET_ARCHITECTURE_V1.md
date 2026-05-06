# CANON Academic Target Architecture v1

This document defines the **final academic target shape** of BusinesAIOS.
It does **not** claim that the repository has already completed migration.

## Canonical layer stack

The final system must converge to the following top-level ownership stack:

- `kernel`
- `domain`
- `application`
- `ports`
- `adapters`
- `entrypoints`
- `bootstrap`
- `observability`
- `governance`
- `security`
- `config`

No additional top-level system owner may be introduced without a documented
canonical reason.

## Canonical execution path

The only end-to-end canonical execution path is:

`RequestOrGoal -> RequestModel -> WorldState -> DecisionCore -> ExecutionPlan -> EffectExecution -> Verification -> Evidence -> MemoryOrStateUpdate`

A narrower runtime enforcement slice may exist for lock tests and service
assembly (`DecisionCore -> GovernanceChain -> ActionExecutor`), but it is only a
**subpath** of the end-to-end canonical flow and must never contradict it.

## Dependency law

Forbidden dependency directions include at minimum:

- `kernel -> runtime`
- `kernel -> adapters`
- `domain -> runtime`
- `domain -> adapters`
- `domain -> entrypoints`
- `application -> concrete adapter implementations`
- `entrypoints -> business logic`
- `recovery -> new decision issuance`
- `learning -> hidden decision issuance`

## Policy-source law

Business thresholds, score weights, limits, caps, confidence mappings,
approval rules, and autonomy tiers must live only in `config/` or in explicit
`domain/policies` owners.
