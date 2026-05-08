from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SurfaceCeiling:
    max_python_files: int
    max_transition_surface_modules: int
    max_path_legacy_compat_shim_files: int


SURFACE_CEILING = SurfaceCeiling(max_python_files=5888, max_transition_surface_modules=8, max_path_legacy_compat_shim_files=5)
_NON_SOURCE_DIR_NAMES = frozenset({".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".runtime", ".artifacts", "artifacts", "data", "runtime_state", "_audit", "htmlcov", "build", "dist"})
_TRANSITION_PATH_TOKENS = ("legacy", "compat", "shim")
_PRODUCTION_EXCLUDED_TOP_LEVEL = frozenset({"tests"})


def is_canonical_source_path(path: Path) -> bool:
    return not any(part in _NON_SOURCE_DIR_NAMES for part in path.parts)


def is_production_source_path(path: Path) -> bool:
    return is_canonical_source_path(path) and (not path.parts or path.parts[0] not in _PRODUCTION_EXCLUDED_TOP_LEVEL)


def iter_canonical_python_files(root: Path):
    for path in root.rglob("*.py"):
        if path.is_file() and is_canonical_source_path(path.relative_to(root)):
            yield path


def iter_production_python_files(root: Path):
    for path in root.rglob("*.py"):
        if path.is_file() and is_production_source_path(path.relative_to(root)):
            yield path


def transition_path_marked_python_files(root: Path) -> tuple[str, ...]:
    return tuple(sorted(path.relative_to(root).as_posix() for path in iter_production_python_files(root) if any(token in path.relative_to(root).as_posix() for token in _TRANSITION_PATH_TOKENS)))


def surface_ceiling_snapshot(root: Path) -> dict[str, object]:
    transition_files = transition_path_marked_python_files(root)
    return {"python_files": count_python_files(root), "transition_path_marked_files": len(transition_files), "transition_files": list(transition_files)}


def count_python_files(root: Path) -> int:
    return sum(1 for _ in iter_production_python_files(root))


def count_path_marked_transition_files(root: Path) -> int:
    return len(transition_path_marked_python_files(root))


__all__ = ["SURFACE_CEILING", "SurfaceCeiling", "count_path_marked_transition_files", "count_python_files", "is_canonical_source_path", "is_production_source_path", "iter_canonical_python_files", "iter_production_python_files", "surface_ceiling_snapshot", "transition_path_marked_python_files"]
