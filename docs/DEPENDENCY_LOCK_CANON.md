# Dependency lock canon

BusinesAIOS keeps two dependency contracts deliberately separate.

## 1. Direct dependency policy lock

`requirements.lock.txt` mirrors `requirements.txt` exactly.

Purpose:

- keep developer and CI direct dependency policy stable;
- detect accidental top-level dependency drift;
- remain lightweight for fast/business-critical gates.

This file is not allowed to contain transitive-only packages.

## 2. Release transitive lock

Release/pre-release gates require one of:

- `requirements.release.lock.txt`
- `uv.lock`
- `poetry.lock`

Purpose:

- prove full resolver output for production/pre-release claims;
- prevent alpha/staging code from being represented as reproducible production release without transitive dependency evidence;
- keep release reproducibility separate from day-to-day top-level dependency policy.

## Generate requirements.release.lock.txt

Preferred:

```bash
bash scripts/ci/generate_release_lock.sh
```

The script uses `uv pip compile` when `uv` is installed, otherwise `pip-compile` from `pip-tools`.

## Verify

Default development/business-critical contract:

```bash
python scripts/ci/check_requirements_lock.py
```

Release/pre-release contract:

```bash
BAIOS_REQUIRE_TRANSITIVE_DEPENDENCY_LOCK=1 python scripts/ci/check_requirements_lock.py
```

## Canon rule

Do not merge transitive package pins into `requirements.lock.txt`. That file is the direct dependency policy mirror. Put resolver output into `requirements.release.lock.txt`, `uv.lock`, or `poetry.lock`.
