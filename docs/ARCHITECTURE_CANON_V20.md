# BUSINESAIOS Architecture Canon v20

This document is the **mandatory architectural law** of the BUSINESAIOS project.

All contributors, AI systems, chats, and developers **must read this document before modifying the codebase**.

No change is allowed to violate this canon.

---

# 1. Absolute rule: NO FUNCTIONALITY LOSS

The project **must never lose functionality**.

Forbidden actions:

- removing working features
- replacing working logic with stubs
- simplifying architecture by deleting behavior
- breaking existing flows
- deleting integrations instead of fixing them
- weakening runtime execution paths
- removing safety systems
- reducing capabilities to simplify code

Allowed:

- refactoring
- modularization
- canonicalization
- improved architecture
- improved observability
- improved safety
- improved extensibility

But **never functional reduction**.

---

# 2. Mandatory reading rule

Every AI system, chat, or developer must:

1. Read this canon
2. Analyze the requested change
3. Verify the change against the canon
4. Implement the change
5. Verify again that the canon is not violated

This rule applies even if modifying **one line of code**.

---

# 3. Core invariants

The system must always maintain:

- One DecisionCore
- One execution contract
- One dataflow
- One infrastructure layer
- One global optimization objective
- Small modules

---

# 4. One DecisionCore

There must be exactly one final decision authority.


core/ai/decision_core.py


Only this module may issue final decisions.

All other modules may:

- produce features
- generate proposals
- evaluate metrics
- execute decisions
- visualize data

But they **must not decide**.

Forbidden:

- secondary decision engines
- planners with final authority
- handlers making decisions
- integrations altering strategy
- runtime modules bypassing DecisionCore

---

# 5. One execution contract

The execution pipeline must always be:


DecisionCore
→ signed action
→ RuntimeGuard
→ RuntimeExecutor
→ Handler
→ EffectPort
→ Event/Audit


Forbidden:

- direct external calls from core
- execution bypassing guard
- multiple executor pipelines

---

# 6. One dataflow

Canonical dataflow:


event
→ event_store
→ ledger/read_models
→ decision input
→ runtime execution
→ audit


Forbidden:

- multiple truth sources
- parallel ledgers
- conflicting metrics
- hidden state stores

---

# 7. Infrastructure ownership

Infrastructure is transitional in older namespaces today, but the final academic owner is:


adapters/*


Forbidden:

- infrastructure in core
- network calls in domain modules
- persistence in UI/policy layers

---

# 8. Single optimization objective

All AI modules must optimize a **single global objective**.

Forbidden:

- multiple independent optimization brains
- conflicting optimizers

---

# 9. Small modules

God modules are forbidden.

Any module exceeding reasonable size must be split into focused components.

---

# 10. Forbidden architectural defects

The following are strictly prohibited:

- duplicated infrastructure
- god modules
- second brain
- hidden business logic
- inconsistent dataflow
- architectural drift
- redundant layers
- synonym namespaces
- scattered configuration
- fake-ready integrations
- mixed sync/async styles
- decorative tests
- copy-paste code duplication
- empty production files
- logging without observability

---

# 11. Mandatory invariant check

Before any change, verify:

- single DecisionCore
- single execution contract
- single dataflow
- unified infrastructure layer
- canonical configuration ownership
- preserved functionality

If any invariant breaks, the change must be rejected.

---

# 12. Final rule

All contributions must **strengthen or preserve the canon**.

Any change weakening the architecture is forbidden.

<!-- SUPER_CANON_WORLD_MODEL_INTEGRITY:START -->
## World Model Integrity & Single-Decision-Brain Contract

### Purpose

BusinesAIOS must preserve exactly one canonical decision brain.

All economics, pricing, LTV, world-model, causal, replay and explainability layers
may enrich, constrain, explain or audit `DecisionCore`, but must never become
a parallel decision issuer.

### Architectural prohibition

The following are forbidden:

- alternative world-model wiring paths into decision issuance
- direct boot/runtime injection of legacy `WorldModel(LTVModel())`
- multiple competing semantic truth sources for decision-time state
- hidden or parallel pricing/economics decision engines
- execution-time use of unpinned model semantics in strict mode

Any such pattern is a **second brain violation**.

### Canonical world-model wiring path

The only canonical path is:

```text
WorldModelStore
→ runtime.boot.world_model_builder.build_default_world_model()
→ CanonicalDecisionWorldModel
→ DecisionCore
→ decision_state_enrichment
→ RuntimeExecutor
```

No other path may provide decision-time world-model semantics.

### DecisionCore contract

DecisionCore is the only final issuance point of business decisions.

Allowed dependency:

`DecisionCore(world_model: DecisionWorldModelPort)`

Forbidden dependencies:

- `DecisionCore(world_model=WorldModel(LTVModel()))`
- `DecisionCore(world_model=<non-canonical direct model>)`

### Status of economics / pricing / world-model layers

These layers are allowed only as:

- feature layers
- constraint layers
- explainability layers
- audit / replay layers

They are forbidden from becoming autonomous decision issuers.

### Pinning and execution integrity

Every decision must carry pinned world-model metadata when available:

- `world_model`
- `world_model_kind`
- `pricing_world_model`
- `pricing_world_model_version`
- `pricing_world_model_hash`
- `pricing_world_state_hash`

Runtime execution must validate pinned metadata against current active model metadata.

If strict pinning is enabled, hash mismatch must reject execution.

### Replay and auditability

The system must support canonical replay of:

- world-model enrichment
- pricing/economics constraints
- causal guardrails
- pinned metadata comparison
- decision trace explanation

A decision that cannot be audited against its model context is not institutionally valid.

### Boot / CI enforcement

Boot must construct the decision world model only through the canonical builder
and verify integrity during startup.

Repository enforcement must include:

- forbidden-path scanner
- typing enforcement for DecisionWorldModelPort
- boot self-check
- tests for pinning, replay and migration
- CI failure on forbidden legacy wiring

<!-- SUPER_CANON_WORLD_MODEL_INTEGRITY:END -->

<!-- CANON_DOMAIN_FILE_SYSTEM_V1:START -->
## Addendum: Strategic Domain File-System Canon

New strategic domains must opt in via:

`core/<domain>/__canon_domain__.py`

and then obey:

- `docs/CANON_DOMAIN_FILE_SYSTEM_V1.md`
- `docs/CANON_NO_GOD_MODULES_V1.md`
- `docs/CANON_RUNTIME_THIN_HANDLERS_V1.md`
- `docs/CANON_BOOT_ORCHESTRATION_V1.md`

These domains are enrichment / constrain / explain / audit / simulation domains only.

They may not:

- issue final decisions
- build direct apply-paths
- bypass DecisionCore
- become a second brain

Root files in canon strategic domains must stay small and role-pure.
<!-- CANON_DOMAIN_FILE_SYSTEM_V1:END -->


## Academic target architecture alignment

The final academic target shape of the project is defined in:

- `docs/CANON_ACADEMIC_TARGET_ARCHITECTURE_V1.md`
- `docs/CANON_NAMESPACE_MIGRATION_MAP_V1.md`
- `canon/academic_target_architecture.py`

This target model resolves legacy ambiguity as follows:

- `boot` is transitional; final ownership is `bootstrap`
- `interfaces` is transitional; final ownership is `entrypoints` and `adapters`
- `interfaces/api` is transitional; final ownership is `entrypoints/api` and `adapters/api/fastapi`
- `runtime` is transitional; final ownership is split across `application`, `adapters`, `entrypoints`, `bootstrap`, `observability`, and `security`
- `core` is transitional; final ownership is split across `kernel`, `domain`, `application`, `ports`, `observability`, `governance`, and `security`

Any older namespace rule must be interpreted as a transitional compatibility rule, not as the final architectural destination.

## Execution-path clarification

The historical runtime service chain

`DecisionCore -> GovernanceChain -> ActionExecutor`

is a **runtime enforcement slice**, not the full canonical business path.

The full canonical path is:

`RequestOrGoal -> RequestModel -> WorldState -> DecisionCore -> ExecutionPlan -> EffectExecution -> Verification -> Evidence -> MemoryOrStateUpdate`

No document or module may treat the narrow runtime slice as permission to bypass world-state construction, verification, evidence, or memory/state update.

## Infrastructure ownership clarification

Older rules that place infrastructure in `interfaces/*` describe a legacy transitional shape only.
The academic target owner for concrete IO, transport, persistence, queue, billing,
connector, and network implementations is `adapters/*`.

`entrypoints/*` may parse external requests and serialize responses, but must not own infrastructure logic or business decisions.

## Policy-source clarification

Business thresholds, score weights, limits, caps, confidence mappings,
approval rules, and autonomy tiers must live only in `config/` or in explicit
`domain/policies` owners. Inline hidden business logic is forbidden.
