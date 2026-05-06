> NON-NORMATIVE DOCUMENT (Appendix).
> Canonical spec: docs/SYSTEM_TZ_CANONICAL.md


# Decision Ring Purity

## Extended execution pipeline

Decision
 → Guard
 → Ledger
 → Capability Resolver
 → Secret‑scoped Executor
 → Side‑effect

## Architectural invariant

- Decision Ring has **no secret access**
- Runtime maps decision → capability → secrets
- ML / replay remain deterministic


See also: `docs/ARCHITECTURE_CANON_V20.md` for the single-brain, single-executor canon.
