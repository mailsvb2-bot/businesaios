from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SurfaceCeiling:
    max_python_files: int
    max_transition_surface_modules: int
    max_path_legacy_compat_shim_files: int


SURFACE_CEILING = SurfaceCeiling(
    max_python_files=5888,
    max_transition_surface_modules=8,
    max_path_legacy_compat_shim_files=5,
)


def count_python_files(root: Path) -> int:
    return sum(1 for path in root.rglob("*.py") if path.is_file())


def count_path_marked_transition_files(root: Path) -> int:
    tokens = ("legacy", "compat", "shim")
    return sum(
        1
        for path in root.rglob("*.py")
        if path.is_file() and any(token in path.as_posix() for token in tokens)
    )


__all__ = [
    "SURFACE_CEILING",
    "SurfaceCeiling",
    "count_path_marked_transition_files",
    "count_python_files",
]
