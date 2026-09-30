# External Intelligence Sovereignty Boundary — Workstream Plan

Status: planned, not implementation-active  
Branch: `canon/external-intelligence-sovereignty-boundary`  
Base: `main`

## Goal

Create one canonical boundary for every external intelligent system connected to BusinessAIOS so that external AI/SaaS/bots/projects can optimize execution mechanics but cannot become a second business decision authority.

This must be provider-agnostic. ClientPlatform will be one consumer, not the architectural owner.

## Existing canonical building blocks to reuse

- DecisionCore — sole final business decision authority.
- ActionIntentV2 — immutable canonical action intent.
- AgentIdentityRegistry — delegated authority, capability/budget/risk/data scopes, revocation.
- Capability Registry — capability/provider truth.
- AutonomyExecutionStep — pre-execution immutable-intent check and runtime authorization.
- ProviderRuntimeWriteGuard — guarded provider writes.
- Existing approval, budget, blast-radius, idempotency, evidence and execution owners.

Do not create a second Decision Core, policy engine, capability registry, execution engine, delegation registry, or provider truth source.

## Confirmed gap

The generic external adapter path still accepts a broad `BusinessExecutionRequest` containing a `BusinessGoalEnvelope`:

```text
BusinessGoalEnvelope
  -> BusinessExecutionRequest
  -> ExternalBusinessAdapter.execute(...)
  -> BusinessExecutionResult
```

That is broader than the canonical execution-only ActionIntent boundary and can permit delegated-domain systems to reinterpret a business goal.

## Target architecture

```text
DecisionCore
  -> signed immutable ActionIntentV2
  -> policy / budget / approval / capability checks
  -> AgentIdentity runtime re-authorization
  -> External Intelligence Sovereignty Boundary
  -> external SaaS / bot / ClientPlatform / agent
  -> ExecutionResult + Evidence only
```

## Canonical invariant

When managed by BusinessAIOS, an external intelligent system may optimize execution mechanics inside explicit delegated scope, but may not independently alter business intent, target, capability, budget, risk scope, policy, approval requirement, expected outcome, or decision provenance.

## Required work

1. Inventory every external execution path that receives BusinessGoalEnvelope, BusinessExecutionRequest, provider payloads, or domain delegation.
2. Classify paths as execution-only, advisory, observe-only, or unsafe delegated-decision surfaces.
3. Define one execution-boundary contract derived from ActionIntentV2; do not invent a parallel intent model.
4. Bind immutable semantic fields: tenant/business/decision/action/intent/goal/agent/capability, material parameters, target, budget ceiling, risk/reversibility, channel scope, deadline, approval evidence, payload hash, expected outcome and provenance.
5. Define explicit permitted local intelligence: transport selection inside allowed set, retry/backoff, rate-limit handling, formatting, protocol adaptation, technical failover, idempotent replay/recovery, media preparation, health/observability.
6. Fail closed on semantic mutation, capability escalation, budget expansion, scope widening, stale approval, revocation, expiry or undelegated side effect.
7. Re-authorize AgentIdentity delegation immediately before every side effect using the existing registry.
8. Treat provider/SaaS outputs as ExecutionResult/Evidence; decision-like provider fields remain untrusted/advisory until a future DecisionCore cycle.
9. Migrate or constrain legacy `ExternalBusinessAdapter.execute(BusinessExecutionRequest)` paths so external systems no longer receive open-ended business decision authority.
10. Preserve standalone mode for products such as ClientPlatform; add governed mode that disables/bypasses their local business-decision authority while retaining transport/runtime intelligence.
11. Add architecture locks preventing new external adapters from bypassing the sovereignty boundary.
12. Add negative tests for changed action type, changed material parameters, changed target, expanded budget, undelegated capability, revoked agent, stale approval, expired intent, forbidden autonomous follow-up and decision-like provider response.
13. Add end-to-end proof with at least one intelligent external provider showing ActionIntent -> governed external execution -> evidence -> feedback, with no alternate decision owner.
14. Verify migration/backward compatibility and provide an explicit deprecation path for broad delegated-domain contracts.
15. Run exact-head CI, Deep Release, architecture/no-second-brain gates, negative-flow tests and post-merge verification before declaring the workstream complete.

## Non-goals

- Do not merge ClientPlatform into BusinessAIOS.
- Do not make providers dumb; local execution intelligence remains allowed.
- Do not implement ClientPlatform-specific sovereignty rules in the canonical layer.
- Do not remove advisory intelligence; only final business decision authority is exclusive.
- Do not weaken existing tests, architecture scanners, approval gates or governance.

## Acceptance criteria

The workstream is complete only when:

- every external side effect can be traced to a valid immutable ActionIntent;
- external systems cannot change protected semantics without a new Decision/ActionIntent;
- delegation and revocation are re-checked at side-effect time;
- external outputs are evidence/results, not executable business decisions;
- no generic external adapter bypass can receive open-ended business authority;
- ClientPlatform and any future intelligent SaaS can plug into the same boundary;
- no second owner/source of truth is introduced;
- exact-head release gates are green.

## Scheduling

Do not implement this workstream while Phase 10 Capability Registry Hardening is incomplete. Resume only after Phase 10 is fully closed and merged.
