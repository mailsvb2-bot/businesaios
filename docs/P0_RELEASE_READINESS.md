# P0 Release Readiness

This document is the operational closure map for the P0 release-readiness gate.
It is intentionally fail-closed: a release can be considered ready only after the
repository produces real evidence, not advisory placeholders.

## P0 contract

A production release requires all of the following to be true:

1. `python -m scripts.ci.cli --gate full` passes.
2. `python -m scripts.ci.cli --gate pre-release` passes.
3. `python -m scripts.ci.cli --gate release` passes.
4. `requirements.lock.txt` is a real transitive lock, not a top-level-only list.
5. A real Postgres database is available and explicitly enabled.
6. Postgres migrations have been applied and recorded.
7. Postgres contract and live probes are ready.
8. A real Docker container has been built and started.
9. `/readyz`, `/storagez`, and `/executionz` are healthy from the running container.
10. `artifacts/ci/staging_runtime_proof.json` and `artifacts/ci/real_runtime_boot_evidence.json` are ready.

## Required server-side command

Run this on the staging server, from the repository root, after installing locked
dependencies and preparing a vetted local Docker base image:

```bash
export DATABASE_URL='postgresql://...'
export BAIOS_PYTHON_BASE_IMAGE='businesaios/python-runtime-base:3.12-slim'
bash scripts/staging/run_staging_runtime_proof.sh
```

The staging runner writes:

- `artifacts/ci/postgres_contract.json`
- `artifacts/ci/postgres_migrations.json`
- `artifacts/ci/postgres_live.json`
- `artifacts/ci/container_runtime_evidence.json`
- `artifacts/ci/container_runtime.json`
- `artifacts/ci/real_runtime_boot_evidence.json`
- `artifacts/ci/production_boot.json`
- `artifacts/ci/staging_runtime_proof.json`

## Release gates

`release` and `pre-release` now require P0 proof environment automatically for
release-proof steps. Those gates set proof flags for Postgres, container runtime,
staging runtime, and production boot. Missing real evidence blocks the gate.

The dependency-lock step also requires a transitive dependency lock during release
and pre-release gates. A top-level-only lock remains acceptable for local/dev and
fast CI, but it is a P0 blocker for production release.

## Stop condition

P0 is closed only when:

- full gate is green;
- pre-release gate is green;
- release gate is green;
- all P0 artifacts above exist and have `status: ready` where applicable;
- no release artifact claims production readiness without real runtime evidence.

Until then the project remains alpha/staging and must not be represented as
production-ready.
