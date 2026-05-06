# Surface ownership pass v5

## What was collapsed

This pass materialized package-root ownership for runtime public surfaces that were still split into `__init__.py` + `public_api.py` pairs.

Collapsed packages:
- `runtime.ads`
- `runtime.ceo`
- `runtime.creative`
- `runtime.governance`
- `runtime.llm`
- `runtime.tenancy`
- `runtime.world_model`

## Why this is safe

- The package root now owns the surface directly.
- Historical imports through `package.public_api` remain available through the existing `runtime.public_api_alias` mechanism.
- No new decision path or alternate business logic owner was introduced.

## Deferred

- `boot.public_api.py`, `core.decision.public_api.py`, and observability public surfaces remain because they still participate in cross-package compatibility and ownership transitions that require a separate pass.
