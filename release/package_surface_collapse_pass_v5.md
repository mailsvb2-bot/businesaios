# Package surface collapse pass v5

This pass collapses package-level `public_api.py` files into the owning package roots where the package itself is already the canonical runtime boundary.

## Collapsed into package owners
- `runtime/ads/public_api.py` -> `runtime/ads/__init__.py`
- `runtime/ceo/public_api.py` -> `runtime/ceo/__init__.py`
- `runtime/creative/public_api.py` -> `runtime/creative/__init__.py`
- `runtime/governance/public_api.py` -> `runtime/governance/__init__.py`
- `runtime/llm/public_api.py` -> `runtime/llm/__init__.py`

## Classification
### Safe to delete
These five `public_api.py` files were thin package-owner surfaces. Historical imports remain available through `install_public_api_alias(__name__)` from the package roots. `runtime.tenancy.public_api` and `runtime.world_model.public_api` were intentionally kept because existing architecture tests treat them as explicit boundary-owner files.

### Safe to rename
None in this pass.

### Do not touch yet without regression risk
- `boot/public_api.py`
- `core/decision/public_api.py`
- `execution/public_api.py`
- `runtime/application/public_api.py`
- `runtime/tenancy/public_api.py`
- `runtime/world_model/public_api.py`
- `observability/public_api.py`
- `observability/platform/public_api.py`
- `observability/platform/observability/public_api.py`

These still participate in transition surfaces or broader import fan-out and need a separate owner-by-owner collapse pass.
