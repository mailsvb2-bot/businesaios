# Business Discovery / Canonical Business Intake — foundation

Status: BD0–BD2 canonical foundation locked; BD3 authenticated workspace/API in progress; BD4 canonical Goal/Constraint orchestration implemented
Branch: `canon/business-discovery-ui-foundation`
Purpose: preserve and implement the missing canonical user-facing intake that feeds the existing BusinessAIOS World Model without creating a second brain.

## Why this exists

The current product onboarding in `frontend/src/App.jsx` creates a business/workspace and collects:
- owner email
- business name
- website
- industry
- city
- business model
- one broad goal
- selected providers
- autonomy mode

That is sufficient for workspace creation, but insufficient for a high-fidelity business model used by economic reasoning, goals/constraints, attribution, experimentation and memory.

There is also older diagnostic onboarding under `core/autopilot/onboarding` that asks about:
- what the business sells
- average check
- margin
- region
- whether sales/clients already exist
- a short test budget
- offer/channel/ads selection

This useful semantic content must be migrated into the canonical business intake instead of becoming or remaining a parallel onboarding authority.

## Architectural laws

1. No second brain.
2. No second World Model.
3. No second Goal or Constraint owner.
4. No duplicate business-profile store.
5. Owner answers are assertions/evidence, not automatically verified truth.
6. Connected-provider observations may confirm, refine or conflict with owner assertions; conflicts must remain visible.
7. Every accepted answer must preserve tenant_id, business_id, actor/source, observed/occurred time and provenance/evidence.
8. UI is a projection and command surface only. It must not become the authority for business truth.
9. Existing canonical owners must be reused:
   - goals: `application.business_goal`
   - constraints: `application.business_constraint`
   - Event Spine / business fact lifecycle: existing ontology/event-store path
   - World Model: existing `core.world_model` builders and canonical state assembly
   - provider truth: existing Business Autonomy provider/capability owners
10. Legacy/older onboarding semantics are migrated, then duplicate authority is removed.

## BD0 canonical ownership map

Business Discovery is an intake/orchestration surface, not a new domain owner. The current field set is bound to the existing owners below and architecture tests must fail if a parallel owner is introduced.

| Concern | Canonical owner / storage | Business Discovery role |
| --- | --- | --- |
| Business identity/profile semantics | `contracts.business_profile`; durable business lifecycle in the existing Business Registry | emit scoped assertions/facts only; never own a second business profile store |
| Business fact chronology | `application.ontology.event_fact_lifecycle.EventFactLifecycleWriter` over canonical EventStore | append schema-versioned owner assertions with provenance and idempotency |
| Current semantic state / World Model input | `runtime.state.StateSynthesisEngine` + canonical StateSnapshotStore | submit observations and consume the synthesized snapshot; never mutate a parallel World Model |
| Evidence | `storage.evidence_store` | write/reuse canonical EvidenceRecord lineage; never create a discovery evidence database |
| Goals | `contracts.business_goal` + sole writer `application.business_goal` | BD4 may propose/create through the existing owner only |
| Constraints | `contracts.business_constraints` + sole writer `application.business_constraint` | BD4 may propose/create through the existing owner only |
| Provider/capability truth | existing Business Autonomy provider/capability owners landed in Phase 10 | drive adaptive questions and reconciliation; UI must not hardcode availability |
| Legacy diagnostic onboarding | `core.autopilot.onboarding` | migration/read source only until parity is proven, then duplicate authority is retired |

The lock test is `tests/arch/test_business_discovery_ownership.py`. It binds the branch to the canonical ontology inventory and rejects local duplicate registry/store classes for Business, Goal, Constraint, Evidence or World Model ownership.

## BD1 field value contract

Known owner answers are fail-closed and normalized before Evidence/EventStore writes:

- identity, market and offer fields are non-empty text;
- money fields are exactly `{"amount_minor": <non-negative integer>, "currency": "<3-letter code>"}`, preserving the existing diagnostic onboarding minor-unit semantics;
- `economics.margin_pct` is numeric and bounded to `0..100`;
- `sales.has_clients` is one of `yes | no | some`;
- epistemic unknown is represented only by `unknown=true` with no concrete value, never by an overloaded string value.

This contract intentionally does not invent a new finance owner. It only validates the shape of owner assertions before those assertions enter the canonical Evidence/Event/State path.

## BD4 canonical Goal/Constraint orchestration

Business Discovery does not own a goal or constraint schema. Authenticated owner commands delegate directly to `BusinessGoalRegistry` and `BusinessConstraintRegistry` over the same canonical Business EventStore and idempotency owner.

- canonical Goal/Constraint creation requires explicit `confirmed=true`;
- authenticated principal identity is recorded as the goal owner / event actor and cannot be supplied by request JSON;
- ambiguous free-text intent is not silently converted into a canonical goal;
- goal constraint links are validated by the existing `BusinessGoalRegistry`;
- replay and identity conflicts remain governed by the existing lifecycle registries.

HTTP surfaces:
- `GET/POST /business-workspace/discovery/goals`
- `GET/POST /business-workspace/discovery/constraints`

## Target vertical slice

Owner opens Business Workspace
→ sees Business Discovery progress
→ answers one adaptive question
→ answer is written through a canonical fact/provenance ingress
→ World Model projects the fact
→ DecisionCore receives the updated state
→ provider evidence can confirm/conflict with the answer
→ World Model changes
→ a later decision can demonstrably change.

No release claim is valid until this vertical slice is proven by integration/E2E tests.

## Discovery domains

### Business identity
- legal/display name
- industry / sub-industry
- business model
- geography / market
- website / public presence

### Offer / product / service
- products/services
- price / average check
- recurring vs one-off
- delivery model
- primary revenue lines

### Customer
- B2B/B2C
- customer segments
- main use cases / pains
- repeat vs new customer mix

### Economics
- approximate revenue
- gross margin / contribution margin where known
- fixed/variable cost hints
- acquisition budget
- CAC/LTV only when known or calculated
- currency

### Sales / funnel
- lead sources
- approximate lead volume
- stages
- conversion hints
- sales cycle
- common loss points

### Operations
- team size / roles
- recurring processes
- bottlenecks
- manual work
- service capacity constraints

### Goals
Business Discovery must create or propose canonical `BusinessGoal` records, not a parallel goal format.

### Constraints
Business Discovery must create or propose canonical `BusinessConstraint` records:
- spending limits
- discount/price limits
- contact-time restrictions
- approval requirements
- prohibited actions
- minimum margin / service-quality bounds

### Integrations
Questions shown to the user must be driven by the canonical Capability Registry/provider truth once Phase 10 lands. The UI must never promise a connector that canonical capability truth marks unavailable.

## Epistemic/provenance model

Initial vocabulary to map onto existing fact/evidence owners during implementation:
- OWNER_ASSERTED
- PROVIDER_OBSERVED
- SYSTEM_DERIVED
- CALCULATED
- INFERRED
- CONFLICTED
- VERIFIED

This document does NOT create a new truth store. Before production code is added, the implementation must map these states onto the existing business-fact/evidence model and ownership inventory.

Example:

Owner answer:
```
metric = average_check
value = 8000 RUB
source = owner
status = OWNER_ASSERTED
```

Later CRM observation:
```
metric = average_check
value = 7640 RUB
source = provider:crm
status = PROVIDER_OBSERVED
```

Reconciliation must preserve both evidence items and derive current business-state truth according to canonical evidence policy; it must not silently overwrite history.

## UX direction

Keep the current four-step account/workspace creation because it is a low-friction entry:
1. О бизнесе
2. Цель
3. Интеграции
4. Режим

After workspace creation, add a persistent card:
`Знакомство с бизнесом — N%`

The discovery experience should be adaptive rather than a single giant form:
- one or a few questions at a time
- explain why a question matters
- allow approximate/unknown answers
- skip questions whose answer can be obtained from a connected provider
- after provider sync, show confirmations/conflicts to the owner
- distinguish "со слов владельца", "подтверждено источником", "рассчитано", "есть конфликт"

## Mandatory implementation order

### BD0 — source-of-truth audit
- map every discovery field to an existing canonical entity/fact owner
- identify missing contracts only after this audit
- lock ownership tests before writes are introduced

### BD1 — canonical owner-assertion ingress
- authenticated tenant/business scope
- idempotency
- provenance/evidence
- fail-closed schema validation
- no direct World Model mutation

### BD2 — projection into World Model
- project accepted assertions through the existing fact/event path
- demonstrate state change without bypassing state assembly

### BD3 — minimal workspace UI
- discovery progress card
- adaptive question renderer
- submit/skip/unknown flows
- recovery/resume across sessions

### BD4 — goals and constraints
- transform explicit owner intent into existing canonical goal/constraint owners
- require confirmation where semantic conversion is ambiguous

### BD5 — provider reconciliation
- compare owner assertions with live provider observations
- expose verified/conflicted status
- preserve evidence lineage

### BD6 — legacy onboarding migration
- migrate useful fields from `core/autopilot/onboarding`
- remove duplicate ownership after parity tests

### BD7 — E2E acceptance
- owner answer → fact/evidence → World Model → DecisionCore
- provider confirmation/conflict → changed World Model
- changed World Model → changed next decision
- tenant isolation
- replay/idempotency
- corruption/recovery
- browser refresh/resume
- no secret persistence in browser storage

## Non-goals

- do not build a separate questionnaire database
- do not put business truth into React state as authority
- do not create an LLM memory store for discovery answers
- do not copy Goal/Constraint entities
- do not hardcode provider availability in the UI
- do not mark inferred values verified without evidence
- do not postpone provenance/reconciliation until after the UI

## Definition of Done

Business Discovery is complete only when:
- the UI exists and resumes safely
- each answer has canonical provenance
- answers affect the canonical World Model
- explicit goals/constraints use their existing owners
- connected providers can confirm/conflict with owner assertions
- DecisionCore consumes the updated state
- the full vertical slice is integration- and user-E2E-tested
- legacy duplicate onboarding authority is removed
- no second source of truth exists
- CI/Canon/ownership/tenant-isolation gates remain green
