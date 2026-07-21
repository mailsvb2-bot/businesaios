"""Passive contracts and repository traversal for the decision-authority scanner."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

GLOBAL_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".runtime",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
    "target",
    "venv",
}
ROOT_EXCLUDED_DIRS = {
    "artifacts",
    "build",
    "data",
    "dist",
    "htmlcov",
    "release_dist",
    "reports",
}

_REFLECTION_LOOKUP_CALLS = frozenset(
    {
        "getattr",
        "builtins.getattr",
        "inspect.getattr_static",
        "object.__getattribute__",
        "type.__getattribute__",
    }
)
_REFLECTION_FACTORY_CALLS = frozenset(
    {
        "operator.attrgetter",
        "operator.methodcaller",
    }
)
_REFLECTION_MUTATION_CALLS = frozenset(
    {
        "setattr",
        "builtins.setattr",
        "delattr",
        "builtins.delattr",
    }
)
_MAPPING_METHODS = frozenset(
    {
        "get",
        "pop",
        "setdefault",
        "update",
    }
)


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    line: int
    detail: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.code}: {self.detail}"


def _validated_repo_root(root: Path | str) -> Path:
    if isinstance(root, str):
        root = Path(root)
    if not isinstance(root, Path):
        raise ValueError("scan root must be a path")
    try:
        resolved = root.expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("scan root must exist") from exc
    if not resolved.is_dir():
        raise ValueError("scan root must be a directory")
    return resolved


def _iter_python_files(root: Path) -> Iterable[Path]:
    repo = _validated_repo_root(root)

    def fail_walk(error: OSError) -> None:
        raise RuntimeError(
            "failed to walk decision-authority scan root"
        ) from error

    for directory, dirnames, filenames in os.walk(
        repo,
        topdown=True,
        onerror=fail_walk,
        followlinks=False,
    ):
        base = Path(directory)
        at_root = base == repo
        dirnames[:] = sorted(
            name
            for name in dirnames
            if not name.startswith(".")
            and name not in GLOBAL_EXCLUDED_DIRS
            and not (at_root and name in ROOT_EXCLUDED_DIRS)
            and not (base / name).is_symlink()
        )
        for filename in sorted(filenames):
            path = base / filename
            if (
                not filename.endswith(".py")
                or path.is_symlink()
                or not path.is_file()
            ):
                continue
            yield path
