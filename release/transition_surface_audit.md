# Transition surface audit

## Completed in this pass

Collapsed package-level public surfaces into owning packages and removed the following split wrappers:
- `headless/public_api.py`
- `crm/public_api.py`
- `runtime/boot/web/fastapi_components/public_api.py`
- `runtime/boot/web/flask_components/public_api.py`
- `runtime/proofs/public_api.py`
- `runtime/world_state/public_api.py`
- `runtime/safety/public_api.py`
- `runtime/human_governance/public_api.py`
- `runtime/knowledge/public_api.py`
- `runtime/finance/public_api.py`
- `runtime/state/public_api.py`

## Safe to delete
These were removed in this pass because the owning package already carries the canonical exports and internal imports were updated:
- `headless/public_api.py`
- `crm/public_api.py`
- `runtime/boot/web/fastapi_components/public_api.py`
- `runtime/boot/web/flask_components/public_api.py`
- `runtime/proofs/public_api.py`
- `runtime/world_state/public_api.py`
- `runtime/safety/public_api.py`
- `runtime/human_governance/public_api.py`
- `runtime/knowledge/public_api.py`
- `runtime/finance/public_api.py`
- `runtime/state/public_api.py`

## Safe to rename
These still represent transition language rather than business logic and can be renamed with controlled import updates:
- `release/compat_legacy_shim_audit.md` -> `release/transition_surface_audit.md` (done)
- `boot/_compat_surface.py` -> `boot/_transition_surface.py`
- `core/decision/_compat.py` -> `core/decision/_transition_surface.py`
- `runtime/application/decision_compat_lock.py` -> `runtime/application/decision_transition_lock.py`

## Do not touch yet without regression-risk work
These are still bound to explicit migration locks, test contracts, or provider naming expectations and need a dedicated wave:
- `canon/legacy/*`
- `core/llm/providers/openai_compat.py`
- `core/offers/catalogs/legacy_catalog.py`
- architecture tests whose purpose is to police transition-surface collapse
- any file where `compat`, `legacy`, or `shim` appears inside a test name that documents a migration invariant

## Notes
The goal of this pass was not blind word replacement. The goal was to shrink real transition surfaces, reduce ownership fragmentation, and keep one canonical owner per runtime boundary.


## Completed in this follow-up pass

Collapsed additional package-owned public surfaces and renamed a few remaining internal transition helpers where imports were fully controlled:
- removed `acquisition/public_api.py`
- removed `app/web/components/public_api.py`
- removed `app/web/pages/public_api.py`
- removed `runtime/actions/public_api.py`
- renamed `boot/_compat_surface.py` -> `boot/_transition_surface.py`
- renamed `runtime/application/decision_compat_lock.py` -> `runtime/application/decision_transition_lock.py`
- renamed `core/decision/_compat.py` -> `core/decision/_transition_surface.py`

## Updated safety split

### Safe to delete
- `acquisition/public_api.py`
- `app/web/components/public_api.py`
- `app/web/pages/public_api.py`
- `runtime/actions/public_api.py`

### Safe to rename
- `boot/_transition_surface.py`
- `runtime/application/decision_transition_lock.py`
- `core/decision/_transition_surface.py`

### Still do not touch yet without regression-risk work
- `core/llm/providers/openai_compat.py`
- `core/offers/catalogs/legacy_catalog.py`
- runtime root `*.public_api` marker files at repository root until import-contract audit is done
- architecture tests that intentionally pin transition markers by exact text
