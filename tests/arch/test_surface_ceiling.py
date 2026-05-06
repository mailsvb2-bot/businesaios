from __future__ import annotations

from pathlib import Path

from canon.surface_ceiling import (
    SURFACE_CEILING,
    count_path_marked_transition_files,
    count_python_files,
)
from canon.transition_surfaces import TRANSITION_SURFACE_MODULES

ROOT = Path(__file__).resolve().parents[2]


def test_repo_python_file_count_stays_below_ceiling() -> None:
    assert count_python_files(ROOT) <= SURFACE_CEILING.max_python_files


def test_transition_surface_registry_stays_below_ceiling() -> None:
    assert len(TRANSITION_SURFACE_MODULES) <= SURFACE_CEILING.max_transition_surface_modules


def test_path_marked_transition_files_stay_below_ceiling() -> None:
    assert count_path_marked_transition_files(ROOT) <= SURFACE_CEILING.max_path_legacy_compat_shim_files
