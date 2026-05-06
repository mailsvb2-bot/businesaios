# PROJECT_FUNCTIONAL_MAP_V1

## 1) Mission and Boundary

Project mission:
- Run one canonical decision-and-execution pipeline for business actions.
- Preserve safety, auditability, and deterministic runtime behavior.
- Prevent second-brain drift (no parallel hidden decision engines).

Hard architectural boundary:
- Decision intent is produced in canonical decision path.
- Execution is performed only through runtime/effects boundary.
- Interfaces (API/Telegram) remain thin and do not own business decisions.

---

## 2) Layer Map (Engineering View)

### A. Boot and Runtime

Primary modules:
- `boot/*`
- `runtime/*`

Responsibilities:
- Build runtime registry and required services.
- Validate boot contract and manifest order.
- Expose typed runtime exports.
- Keep construction of critical classes factory-controlled.

Key guarantees:
- No manual wiring bypasses outside boot.
- Single source of runtime service naming and registration.

### B. Application and Decision Surface

Primary modules:
- `runtime/application/*`
- canonical decision/core policy modules under `core/*` (advisory/decision surfaces)

Responsibilities:
- Accept decision input, produce structured recommendation/command intent.
- Keep recommendation stage pure (no side effects).

Key guarantees:
- No transport payload reconstruction in recommendation stage.
- No hidden direct execution in decision components.

### C. Effects and Integrations

Primary modules:
- `runtime/_internal/effects_*`
- `interfaces/ads/*`
- infra integration bridges under `core/behavior/integration/*`

Responsibilities:
- Execute side effects through controlled effects ports.
- Encapsulate external provider specifics.

Key guarantees:
- No uncontrolled network markers outside sealed zones.
- Integration code remains in designated adapters/connectors.

### D. Interfaces

Primary modules:
- `interfaces/api/*`
- `interfaces/telegram/*`
- `interfaces/behavior/*`

Responsibilities:
- Parse input, call application service, present output.
- Keep delivery/channel concerns separate from decision logic.

Key guarantees:
- Route handlers do not access runtime internals directly.
- Telegram runner uses application service contract.

### E. Infra, Governance, Compliance

Primary modules:
- `infra/*`

Responsibilities:
- Lifecycle, retries, idempotency, readiness and process control.
- Governance approvals, evidence, policy versioning, rollout/rollback.
- Control-plane and compliance/audit services.

Key guarantees:
- Boot modules in infra do not build runtime directly.
- Governance and evidence are split into explicit bounded modules.

### F. Behavior Engine

Primary modules:
- `core/behavior/contracts/*`
- `core/behavior/math/*`
- `core/behavior/operators/*`
- `core/behavior/builders/*`
- `core/behavior/observables/*`
- `core/behavior/constraints/*`
- `core/behavior/read_models/*`
- `core/behavior/operator_catalogs/*`
- `core/behavior/operator_policy_catalogs/*`
- `core/behavior/guards/*`
- `core/behavior/runtime/*`
- `core/behavior/persistence/*`
- `core/behavior/integration/*`

Responsibilities:
- Build behavioral state from events.
- Apply bounded operator math (Dirac-like spinor domain).
- Produce non-executable constraints and observables.
- Bridge behavior safely into pricing/offer/retention/runtime.

Key guarantees:
- Behavior payload remains non-executable by contract.
- Hidden offer selection keys are explicitly forbidden.
- Policy denials are audited and observable.

### G. Observability

Primary modules:
- `observability/*`
- telemetry bridges in behavior and runtime boot observability modules

Responsibilities:
- Structured metrics/traces/events export.
- Provide operational visibility for runtime and policy denials.

---

## 3) Functional Flow (End-to-End)

1. User/system event enters through `interfaces/api` or `interfaces/telegram`.
2. Interface converts request into application contract.
3. `boot`-initialized application service routes request into canonical decision path.
4. Decision/recommendation is produced in pure stage.
5. Runtime executes side effects through registered effects ports and connectors.
6. Infra control-plane/governance checks may gate, approve, delay, rollback, or escalate.
7. Observability and audit trails are emitted.
8. Interface returns response to user/operator.

---

## 4) User-Facing Functional Capabilities

- Multi-channel interaction via API and Telegram.
- Controlled automated actions with strict safety boundaries.
- Governance-aware operation:
  - approvals,
  - policy/version controls,
  - promotion/rollback,
  - constitutional/evidence tracking.
- Reliable behavior under load/failure:
  - retries,
  - idempotency,
  - readiness checks,
  - graceful lifecycle handling.
- Transparent operator experience through audit and telemetry surfaces.

---

## 5) Architectural Locks and Invariants

Enforced by test packs in `tests/arch` and related strict tests:
- Single decision center (no second brain).
- No hidden business logic in disallowed layers.
- No direct runtime registry abuse outside allowed zones.
- No manual instantiation of sealed critical runtime classes.
- No forbidden network/integration usage outside sealed effect boundaries.
- Domain file system canon rules (structure, artifacts, required files).
- Release attestation via `release/manifest.json`.

Operational interpretation:
- Any new module must fit an existing layer role.
- Any cross-layer call must follow canonical dependency direction.
- Compatibility shims remain thin aliases only (no business logic).

---

## 6) Compatibility and Legacy Policy

Current policy:
- Canonical modules host real implementation.
- Legacy modules are allowed only as explicit thin alias-shims when needed.
- New feature work must not introduce new `legacy`/`compat` logic branches.
- Remove legacy surfaces only after zero-import proof + green regression.

---

## 7) Engineering Quality Gates

Mandatory gates for meaningful changes:
- `pytest -q tests/arch`
- `pytest -q --maxfail=20`
- Artifact hygiene (`__pycache__`, `.pyc`, tool caches removed before release checks)
- `release/manifest.json` regeneration and verification when file set changes

Recommended additional gate:
- Targeted test packs for touched functional domain (behavior, infra, interfaces, ads, etc.).

---

## 8) Roadmap Focus (Safe Expansion)

Safe next expansion areas:
- Deepen behavior catalogs/policy catalogs with stronger schema validation.
- Expand governance evidence and operator session analytics.
- Continue legacy retirement where canonical equivalents are already proven.
- Keep interface surfaces thin while improving UX and observability.

Non-negotiable constraint:
- No second decision path, no hidden execution, no untracked side effects.
