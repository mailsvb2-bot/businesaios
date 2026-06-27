# Maintenance E402 wave 1

Small maintenance-only cleanup.

Scope:

- `scripts/maintenance/reduce_ruff_debt.py`
- `scripts/maintenance/reduce_ruff_debt_no_f401.py`
- `scripts/maintenance/ruff_debt_factory_imports_compat.py`
- `scripts/maintenance/ruff_debt_factory_simple_compat.py`

Intent:

- remove module-level imports that happen after `sys.path` bootstrap;
- keep imports local to helper functions;
- avoid runtime, DecisionCore, workflows, release gates, generated artifacts, and public API changes.

Blocked from this wave by connector safety layer and intentionally left untouched:

- `scripts/maintenance/ruff_debt_factory_typing_compat.py`
- `scripts/maintenance/ruff_debt_factory_typing_core_compat.py`
- `scripts/maintenance/run_guarded_ruff_debt_factory.py`
