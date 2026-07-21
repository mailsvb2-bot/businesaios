"""Passive contracts and repository traversal for the decision-authority scanner."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from canon.repository_sources import (
    DEFAULT_EXCLUDED_DIR_NAMES,
    DEFAULT_ROOT_EXCLUDED_DIR_NAMES,
    iter_repository_python_files,
    validate_repository_root,
)

GLOBAL_EXCLUDED_DIRS = set(DEFAULT_EXCLUDED_DIR_NAMES)
ROOT_EXCLUDED_DIRS = set(DEFAULT_ROOT_EXCLUDED_DIR_NAMES)

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
    try:
        return validate_repository_root(root)
    except ValueError as exc:
        message = str(exc).replace("repository root", "scan root")
        raise ValueError(message) from exc


def _iter_python_files(root: Path) -> Iterable[Path]:
    yield from iter_repository_python_files(root)
