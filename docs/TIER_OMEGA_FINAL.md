# Tier‑Ω FINAL (spec addendum)

> NON-NORMATIVE DOCUMENT (Appendix).
> Canonical spec: docs/SYSTEM_TZ_CANONICAL.md


## Execution pipeline (final)
Decision
 → Guard
 → Ledger
 → Capability Resolver
 → Secret‑scoped Executor
 → Side‑effect

## Formal layer
- `formal/decision_core.tla` — side‑effects require commit
- `formal/governance.tla` — governance actions are safe
- `formal/rl_economy.tla` — economy invariants + governance freeze

## Zero‑trust decision making
- Multi‑region signing (`runtime/security/multiregion_signing.py`)
- Signed quorum gate (`core/consensus/bft_signed_quorum.py`)

## Control‑plane
- `runtime/governance/control_plane.py` — self‑healing governance skeleton
