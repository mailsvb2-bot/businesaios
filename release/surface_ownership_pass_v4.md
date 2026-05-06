# Surface ownership pass v4

This pass continues the collapse of redundant public surfaces without removing domain behavior.

## Safely removed in this pass

- `acquisition/public_api.py`
- `runtime/queue/public_api.py`
- `runtime/observability/public_api.py`

These files were redundant with package-root owners that already publish the same symbols and install `public_api` aliases. Historical imports such as `from acquisition.public_api import ...` remain valid through the package alias mechanism.

## Safe to rename later

These files are thin transition helpers and can be renamed in a dedicated pass once tests are updated in one wave:

- `boot/_compat_surface.py`
- `core/decision/_compat.py`
- `runtime/application/decision_compat_lock.py`

## Do not touch yet without a regression pass

These areas still carry real compatibility semantics or external contract risk:

- `boot/public_api.py`
- `core/decision/public_api.py`
- `observability/public_api.py`
- `observability/platform/public_api.py`
- `runtime/ads/public_api.py`
- `runtime/application/public_api.py`
- `runtime/ceo/public_api.py`
- `runtime/creative/public_api.py`
- `runtime/governance/public_api.py`
- `runtime/llm/public_api.py`
- `runtime/tenancy/public_api.py`
- `runtime/world_model/public_api.py`
- `catalog.py` files that serve as real registry owners rather than wrappers

## Why this pass is safe

- No business logic was moved into new owners.
- No second decision path was introduced.
- Existing import contracts are preserved through package-level aliasing.
- The change only removes redundant surfaces where the package root already owned the public namespace.
