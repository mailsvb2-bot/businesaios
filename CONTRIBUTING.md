# BUSINESAIOS Contribution Rules

All contributors and AI systems must follow these rules.

---

# 1. Mandatory first step

Before making any modification:

1. Read `docs/ARCHITECTURE_CANON_V20.md`
2. Confirm that your change respects the canon
3. Confirm that no functionality is lost

---

# 2. Forbidden actions

Never:

- remove functionality
- create a second decision engine
- duplicate infrastructure
- introduce hidden business rules
- bypass runtime execution path
- create new architectural layers without justification
- introduce fake integrations
- add silent exception handling
- weaken observability

---

# 3. Required checks before committing

Every change must verify:

- DecisionCore remains unique
- runtime execution path unchanged
- dataflow remains canonical
- configs not duplicated
- no god modules introduced
- tests remain meaningful

---

# 4. Tests must enforce architecture

Architecture rules must be enforced via tests.

If a test fails, the architecture must be corrected.

Tests must detect:

- second brain
- duplicate layers
- hidden logic
- silent failures
- config duplication
- execution bypass

---

# 5. Functionality preservation

Refactoring must **not remove behavior**.

If a module is replaced, the new implementation must support the same functionality.

---

# 6. AI assistance rules

When AI tools are used:

- they must read the Architecture Canon first
- they must not simplify architecture by deleting behavior
- they must not introduce alternate pipelines
- they must not weaken the system

---

# 7. Final requirement

All contributions must:

- preserve functionality
- preserve architecture
- increase maintainability

<!-- SUPER_CANON_WORLD_MODEL_INTEGRITY:START -->
8. World-model integrity is mandatory

Every contributor, chat, or AI system must additionally verify:

- there is still exactly one canonical world-model path into DecisionCore
- pricing / economics / replay layers did not become a second brain
- decisions remain pinned to world-model metadata
- strict pinning failures are not bypassed
- replay and auditability are preserved
- boot self-check / CI integrity checks still work

Changes that weaken these guarantees are forbidden.

<!-- SUPER_CANON_WORLD_MODEL_INTEGRITY:END -->

## Canon strategic domains

Canon strategic domains must opt in via `__canon_domain__.py` and then obey:

- `docs/CANON_DOMAIN_FILE_SYSTEM_V1.md`
- `docs/CANON_NO_GOD_MODULES_V1.md`
- `docs/CANON_RUNTIME_THIN_HANDLERS_V1.md`
- `docs/CANON_BOOT_ORCHESTRATION_V1.md`

These domains are enrichment / constrain / explain / audit domains only.
They must never become hidden decision issuers.
