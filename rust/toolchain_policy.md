# Rust safety-core toolchain policy

BusinessAIOS uses Rust only as a pure safety-verification kernel. Rust must not become a second DecisionCore, second policy engine, database layer, network layer, AI/planning layer, or hidden execution path.

## Minimum supported Rust toolchain

- MSRV: Rust/Cargo `1.75.0`.
- Edition: `2021` only.
- `edition2024` is forbidden until explicitly approved through the canonical safety/dependency review.

## Dependency policy

The `businessaios_safety_core` crate is part of release safety gates. Its dependency graph must stay deterministic and small.

Allowed runtime dependencies:

- `serde`
- `serde_json`

Allowed transitive dependencies are the packages currently locked by `rust/businessaios_safety_core/Cargo.lock` for the allowlisted runtime dependencies.

Rules:

1. `Cargo.lock` must be committed.
2. `target/` must never be tracked by Git.
3. New Rust dependencies are forbidden unless they include:
   - MSRV compatibility proof for Rust/Cargo 1.75.0;
   - lockfile update;
   - license/supply-chain review;
   - no DB/network/runtime side effects;
   - no second-brain or parallel policy-engine behavior;
   - admin/control-plane visibility when runtime behavior is affected.
4. Direct FFI is not enabled by this policy.
5. Runtime Python owner guards remain the execution-path owners.

## Canon boundaries

Rust safety-core may validate pure invariants only:

- tenant/business scope;
- money minor-units;
- budget/refund;
- blast radius;
- idempotency transitions;
- outbox transitions;
- shared golden fixture parity.

Rust safety-core must not decide business strategy, planning, AI behavior, approval workflow, orchestration, API routing, persistence, or execution side effects.
