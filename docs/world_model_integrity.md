# World Model Integrity Contract

## Goal

DecisionCore must depend on exactly one canonical world-model wiring path.

## Allowed path

WorldModelStore
→ `runtime.boot.world_model_builder.build_default_world_model()`
→ `CanonicalDecisionWorldModel`
→ `DecisionCore(world_model=...)`

## Forbidden paths

The following are forbidden in runtime/boot/decision wiring:

- direct `WorldModel(LTVModel())`
- direct import of legacy `WorldModel` into boot/runtime assembly
- direct `world_model=WorldModel(...)` injection

## Enforcement

The repository enforces this via:

- `runtime.boot.world_model_contract.DecisionWorldModelPort`
- `runtime.boot.world_model_boot_check`
- `runtime.boot.world_model_self_check`
- `runtime.boot.world_model_forbidden_paths`
- `scripts/check_world_model_integrity.py`
- `scripts/check_world_model_typing.py`
- CI workflow `world-model-integrity`

## Migration

Use:

```bash
python scripts/migrate_world_model_to_canonical.py
```

Then run:

```bash
python scripts/check_world_model_integrity.py
python scripts/check_world_model_typing.py
pytest -q tests/test_world_model_*.py tests/test_canonical_decision_world_model*.py tests/test_migrate_world_model_to_canonical.py
```
