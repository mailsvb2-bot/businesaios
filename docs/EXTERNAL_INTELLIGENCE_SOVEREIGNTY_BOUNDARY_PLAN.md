# External Intelligence Sovereignty Boundary — Workstream Plan

Status: implementation complete; production-adapter acceptance proof added; exact-head release verification is a mandatory merge gate
Branch: `canon/external-intelligence-sovereignty-closure`
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

## Resolved gap

The original generic external adapter path accepted a broad `BusinessExecutionRequest` containing a `BusinessGoalEnvelope`:

```text
BusinessGoalEnvelope
  -> BusinessExecutionRequest
  -> ExternalBusinessAdapter.execute(...)
  -> BusinessExecutionResult
```

That surface was broader than the canonical execution-only ActionIntent boundary and could permit delegated-domain systems to reinterpret a business goal. Managed intelligent execution now crosses the boundary only through `ExternalExecutionRequest(ActionIntentV2)`; the legacy broad request remains limited to non-managed compatibility modes.

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

## Legacy delegated-call audit

The compatibility surface has been classified and constrained as follows:

- **Managed intelligent domain execution** — `DOMAIN_AI`, `DOMAIN_PLANNER`, and `DOMAIN_SCHEDULER` are selected by `BusinessAutonomyPolicy` as `POLICY_GUARDED_DELEGATED`; `BusinessAutonomyService` intercepts that mode and exposes only `ExternalExecutionRequest(ActionIntentV2)` to the external adapter.
- **Managed channel compatibility projection** — `ChannelBackedBusinessAdapter.execute_intent(...)` may build an internal `BusinessExecutionRequest` only from immutable `ActionIntentV2` fields. The original broad goal envelope is not forwarded to the external intelligent system.
- **Observe/simulation** — simulation is forced to `OBSERVE_ONLY`; broad compatibility DTOs may remain because the path performs no live external decision/effect.
- **Supervised/human-owned and low-autonomy non-AI compatibility** — broad `BusinessExecutionRequest` remains supported for backward compatibility, but these modes are outside the intelligent delegated-domain authority path.
- **Governance alignment preview** — route-handler construction of a delegated request is advisory/read-only and is passed to the alignment bridge, not to an executing adapter.
- **Provider result fields that resemble decisions** — retained only as provider evidence; the managed boundary overwrites authority metadata with `decision_authority=False` and `external_output_role=execution_result_evidence`.

Architecture locks enforce the first two invariants so a future intelligent adapter cannot silently fall back to `execute(BusinessExecutionRequest)`.

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

## Production-adapter acceptance evidence

The final acceptance gap is covered by
`tests/integration/test_external_intelligence_sovereignty_production_adapter.py`.

The proof uses the production `LiveApiBusinessChannelAdapter` and its real injected
transport contract rather than the unit-test `_Adapter`. It verifies the complete
governed path:

```text
canonical decision.proposed provenance
  -> ActionIntentV2
  -> AgentIdentity runtime re-authorization
  -> BusinessAutonomy policy forces POLICY_GUARDED_DELEGATED
  -> ChannelBackedBusinessAdapter sovereign projection
  -> LiveApiBusinessChannelAdapter
  -> external provider transport
  -> provider evidence/result
  -> non-authoritative result normalization
  -> guarded evidence sink + planning feedback sink
```

The provider is deliberately allowed to return a decision-like
`provider_proposed_next_action` and to claim `decision_authority=True`.
BusinessAIOS preserves the proposal only as evidence, overwrites
`decision_authority=False`, marks the output as
`execution_result_evidence`, and performs no autonomous follow-up call.

The same proof also asserts that the original broad business goal is not forwarded
to the provider: the production adapter receives only the parameters projected
from the approved immutable `ActionIntentV2`.

Local acceptance evidence on the closure branch:

- production-adapter integration proof: green;
- external-intelligence sovereignty suite: green;
- AGI no-second-brain architecture lock: green;
- canonical anti-second-brain rules: green;
- second-brain alias scan: green;
- Ruff on the new integration proof: green;
- Python compile check on the new integration proof: green.

Exact-head GitHub release gates remain the final merge prerequisite and must not be
bypassed.

## Scheduling

Do not implement this workstream while Phase 10 Capability Registry Hardening is incomplete. Resume only after Phase 10 is fully closed and merged.
