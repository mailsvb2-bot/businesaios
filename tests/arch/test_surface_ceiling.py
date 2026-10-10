from __future__ import annotations

import json
from pathlib import Path

from canon.surface_ceiling import (
    SURFACE_CEILING,
    count_path_marked_transition_files,
    count_python_files,
)
from canon.transition_surfaces import TRANSITION_SURFACE_MODULES

ROOT = Path(__file__).resolve().parents[2]


def _phase18_python_file_budget() -> int:
    ledger = json.loads((ROOT / "canon" / "metrics_debt_ledger.json").read_text(encoding="utf-8"))
    policy = ledger.get("phase18_absorption_growth_policy") or {}
    return int(policy.get("python_file_budget", 0)) if policy.get("active") is True else 0


def test_repo_python_file_count_stays_below_ceiling() -> None:
    assert count_python_files(ROOT) <= SURFACE_CEILING.max_python_files + _phase18_python_file_budget()


def test_transition_surface_registry_stays_below_ceiling() -> None:
    assert len(TRANSITION_SURFACE_MODULES) <= SURFACE_CEILING.max_transition_surface_modules


def test_path_marked_transition_files_stay_below_ceiling() -> None:
    assert count_path_marked_transition_files(ROOT) <= SURFACE_CEILING.max_path_legacy_compat_shim_files
