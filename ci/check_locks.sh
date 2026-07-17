#!/usr/bin/env bash
set -euo pipefail

# Bounded canonical lock gate.
# Do not run the repository-wide historical `-m lock` suite here: that path is
# intentionally heavy and belongs to full/release audits. This script mirrors
# the curated P0 lock target set used by `python -m scripts.ci.cli --gate fast`.

export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PYTHONDONTWRITEBYTECODE=1

PYTHON_BIN="${PYTHON_BIN:-python}"

PYTEST_TARGETS=(
  tests/p0/test_startup_hooks_lightweight.py
  tests/p0/test_ci_gate_plan_is_bounded.py
  tests/lock/test_no_merge_conflict_markers.py
  tests/lock/test_no_patch_artifacts_extended.py
  tests/lock/test_no_reject_artifacts.py
  tests/lock/test_super_locks_no_zip_sqlite.py
  tests/lock/test_super_locks_bytescan.py
  tests/lock/test_lock_cicd_contract_files_present.py
  tests/lock/test_github_workflow_supply_chain.py
  tests/lock/test_deep_release_workflow_contract.py
  tests/lock/test_runtime_release_package_hygiene.py
  tests/lock/test_ai_ceo_no_second_path.py
  tests/lock/test_runtime_actions_registry_lock.py
  tests/arch/test_agi_no_second_brain_surfaces.py
)

PYTEST_ARGS=(
  -q
  --strict-markers
  --strict-config
  --tb=short
  -p
  pytest_asyncio.plugin
  -m "not slow"
  "${PYTEST_TARGETS[@]}"
)

echo "[locks] running bounded P0 lock suite with $PYTHON_BIN"
"$PYTHON_BIN" -m pytest "${PYTEST_ARGS[@]}"
