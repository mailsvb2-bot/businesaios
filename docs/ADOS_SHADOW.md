# ADOS shadow integration (Phase 1)

This is an **advisory-only** integration of ADOS 0.6.0 into BusinessAIOS.
It was prepared against BusinessAIOS `main` commit
`64e937e024940ef082bfbbff9be23c27236eefa2` (tree
`109a0d0886cdb6248bdd1320185aa45c7a1f6d74`). The patch is add-only and
intentionally does not change the existing CI, Deep Release Validation,
Trusted Production Certification, deploy scripts, or production runtime.

## What the shadow workflow does

For a pull request, `ADOS Shadow` checks out the exact candidate SHA, preserves
full Git history, verifies the vendored ADOS wheel, creates two isolated Python
environments, calculates the exact base...head diff (including renames and
deletions), and asks ADOS to assess the change as a strict `MERGE` lane.

The result is rendered as `WOULD_ALLOW` or `WOULD_BLOCK` in the job summary.
A valid ADOS assessment always leaves the **shadow workflow green**, including
when strict ADOS would block. Only an infrastructure/invalid-JSON failure makes
the advisory workflow fail.

## Reused BusinessAIOS proof

| ADOS gate | Existing BusinessAIOS measurement |
|---|---|
| `architecture` | canonical `scripts.ci.cli --gate fast` (includes architecture-bypass scan, quality/lock/import/boot/regression-impact checks) |
| `tests` | canonical `--gate business-critical` |
| `security` | `pytest tests/security` + canonical `--gate rust-safety` |
| `contracts` | `pytest tests/contracts` |
| `integration` | canonical `--gate full` |
| `user_journey` | canonical `--gate acceptance` |
| `data_migration` | canonical `--gate postgres-migrations` against disposable PostgreSQL |
| `full_regression` | canonical `--gate full` |

The migration gate is a real migration execution. The stronger PostgreSQL
backup/restore proof remains owned by **Deep Release Validation** and is not
misrepresented as a shadow migration PASS.

## Deliberate UNKNOWN gates

`red_team` and the strict ADOS `dependency_audit` are intentionally not
registered in Phase 1. BusinessAIOS already has meaningful security, lock and
Rust supply-chain proof, but those are not renamed into a different ADOS
assurance contract merely to make the dashboard green.

Therefore, for example, a payment/billing or sensitive security change can
produce `red_team=UNKNOWN` and `WOULD_BLOCK`. That is expected shadow evidence,
not a CI failure.

## Product/runtime dependency isolation

BusinessAIOS currently locks `cryptography==49.0.0`. ADOS 0.6.0 declares
`cryptography>=43,<47`. The shadow workflow therefore uses:

- `.ados-project-venv` for BusinessAIOS and its own `requirements.lock.txt`;
- `.ados-control-venv` for ADOS with exactly `cryptography==46.0.4`.

The ADOS integration **does not downgrade or replace BusinessAIOS runtime
dependencies**.

The vendored ADOS wheel is SHA-256 verified as:

`d00bc809685bd47f02d25ec84dd232996214be2ac2dbfa7a6d2c0b587925e85d`

## Release boundary

Phase 1 does not build, sign, certify or deploy a release. `.ados/build.json`
explicitly refuses release operation. Existing **Deep Release Validation** and
**Trusted Production Certification** remain authoritative for migration
backup/restore, staging runtime proof, exact-SHA release evidence, production
synthetics and optional physical-Windows evidence.

## Promotion criteria

Do not turn ADOS into a required merge/release status until shadow evidence has
been observed on real PRs, impact noise has been corrected, `dependency_audit`
and `red_team` have real independent measurements, controller dependencies are
fully offline/hash-locked, independent signing/runner/scanner trust is wired,
and repository branch/ruleset protection explicitly requires the intended
ADOS status.

A required MERGE gate and a production RELEASE gate are separate later phases.
