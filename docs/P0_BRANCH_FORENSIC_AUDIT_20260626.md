# P0 branch forensic audit — 2026-06-26

Source preserved on GitHub:

- `backup/p0-release-readiness-hardening-20260626T174221Z`
- preserved head: `05ad107ce37fb10a3bc6dfd3415920bc8e528600`

## Verdict

This backup branch must not be merged wholesale. It is useful as a forensic source, but it is mixed: it contains production-readiness work, support-platform/RL scaffolding, workflow drift, generated/runtime artifacts, compatibility shims, and stale tree differences against current `main`.

Useful work must be extracted only as small bounded PRs.

## Already extracted into `main`

The following value has already been extracted and merged:

1. P0 release-readiness gate hardening — PR #67.
2. Billing recovery/refund/platform hardening — PR #68.

Do not re-extract these broad slices from the backup branch.

## Current backup-vs-main finding

The preserved backup branch is not the same as a clean feature branch against current `main`. A direct tree diff shows hundreds of paths because current `main` and the backup diverged. Some apparent deletions are merely files that now exist in `main` but not in the backup. Some apparent additions are support-platform files that existed in the backup but are currently represented in `main` through package-level owners and import-door compatibility.

Therefore, raw checkout from the backup branch is forbidden.

## Useful extraction candidates

### Candidate A — explicit runtime support modules vs dynamic import doors

The backup contains many explicit files under `runtime/platform/support/...` while current `main` keeps a dynamic import-door bridge:

- `runtime/platform/support/import_doors.py`
- `runtime/platform/support/import_doors_registry.json`
- auto-install in `runtime/platform/support/__init__.py`

Potential value:

- reduce hidden dynamic import behavior;
- remove meta-path magic;
- make module ownership visible to static analysis;
- reduce architecture drift risk.

Risk:

- many backup support files are thin compatibility wrappers;
- adding them all would increase mass heavily;
- package-level owners may already be the cleaner implementation;
- this must be done domain-by-domain, not as a bulk restore.

Safe extraction shape:

1. Pick one tiny support domain.
2. Add explicit modules only if they remove a dynamic import-door entry.
3. Delete the corresponding import-door registry entries in the same PR.
4. Prove imports still work with focused tests.

Priority domains:

- `runtime.platform.support.governance`
- `runtime.platform.support.safety.runtime`
- `runtime.platform.support.security`
- `runtime.platform.support.events`

### Candidate B — support safety contracts

Backup support safety runtime has simple classes such as emergency stop, degraded mode, human override, reward-hacking detector, runaway feedback firewall, and safe shutdown. These are conceptually useful, but should be normalized into canonical runtime guard/safety surfaces rather than copied as RL-support shims.

Safe extraction shape:

- extract only contracts/tests first;
- no new execution path;
- no second DecisionCore;
- no autonomous action outside `RuntimeGuard -> Ledger -> RuntimeExecutor`.

### Candidate C — governance release-readiness aliases

Backup contains small governance module files like `release_readiness.py` importing owner classes from package `__init__`. These improve import compatibility but are also shim-like.

Safe extraction shape:

- avoid unless a real import is broken;
- prefer removing import-door dependency over adding cosmetic wrappers;
- require an explicit import test per restored module.

## Rejected by default

Reject these from backup unless a later audit proves a very specific need:

- branch-wide workflow changes;
- `release/manifest.json` churn;
- generated `runtime/data/security/*.jsonl` artifacts;
- stale `conftest.py` changes;
- `gitignore` replacement/addition anomalies;
- `multipart.py` compatibility hack;
- bulk `runtime/platform/support` restore;
- any removal of current `main` contracts, tests, storage compatibility, or billing recovery contracts.

## Extraction rules

Every extraction PR from this backup must satisfy:

1. Base from current `main`.
2. One bounded domain only.
3. No raw checkout of files over `main`.
4. No deletions unless the PR removes an explicitly replaced dynamic import-door surface.
5. No generated artifacts.
6. No broad workflow edits.
7. Run focused tests plus `python -m scripts.ci.cli --gate fast` before merge.
8. Keep the project status honest: alpha/staging until real P0 runtime evidence exists.

## Proposed next PR

Create a tiny PR for one import-door replacement slice, starting with governance because it is low risk and has package-level owner classes already in `runtime/platform/support/governance/__init__.py`.

Scope should be limited to:

- a small set of explicit governance module files;
- removal of matching entries from `runtime/platform/support/import_doors_registry.json` only if covered by tests;
- import tests proving the public paths work without meta-path import doors.

Do not touch runtime execution, DecisionCore, workflows, generated artifacts, or release manifest in that PR.
