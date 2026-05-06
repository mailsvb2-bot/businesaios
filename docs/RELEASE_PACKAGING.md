# Release packaging (clean zip)

A release ZIP must **never** include:
- `__pycache__/`
- `*.pyc`
- local SQLite / runtime databases (e.g. `runtime/entrypoints/data/*.db`)

## One-command packager

From repo root:

```bash
python scripts/package_release.py
```

It will create:

- `BUSINESAIOS_RELEASE_CLEAN.zip`

## What it excludes

- Python caches: `__pycache__`, `*.pyc`, test/mypy/ruff caches
- Any `*.db`, `*.sqlite*` files (including `runtime/entrypoints/data/`)
- Git metadata

## Why runtime DBs are excluded

They are **environment state**, not source code.
Shipping them can:
- leak data
- break determinism
- create hard-to-debug "it works on my machine" behavior
