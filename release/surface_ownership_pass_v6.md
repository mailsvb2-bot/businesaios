# Surface ownership pass v6

## What was collapsed

This pass removed another package-root/public_api split where the package root
already represented the real owner surface and a separate ``public_api.py`` only
added transitional noise.

### Removed safely
- `runtime/tenancy/public_api.py` → owner is `runtime/tenancy/__init__.py`
- `runtime/world_model/public_api.py` → owner is `runtime/world_model/__init__.py`
- `observability/public_api.py` → owner is `observability/__init__.py`
- `observability/platform/public_api.py` → owner is `observability/platform/__init__.py`
- `observability/platform/observability/public_api.py` → owner is `observability/platform/observability/__init__.py`

These removals preserve historical imports by installing the standard
`public_api` alias at the owning package root.

## Remaining compat / legacy / shim classification

### Safe to delete
- package-level `public_api.py` wrappers when the package root already exports the same symbols and installs a `public_api` alias
- duplicate test-only path comments that point at removed split surfaces

### Safe to rename
- purely explanatory marker constants that still use the word `compat` but only describe transition status
- audit docs that describe a transition surface but do not participate in imports

### Not safe to touch yet
- `boot/public_api.py` because it still carries boot-specific lazy delegation semantics
- `core/decision/public_api.py` because it remains a compatibility bridge to the single runtime.application owner
- `runtime/application/public_api.py` because arch locks and owner semantics still centralize here
- `execution/public_api.py` because it is a large explicit export owner, not just a thin wrapper
- `catalog.py` modules that act as real registries/contracts rather than re-export wrappers
