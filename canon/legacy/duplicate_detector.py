from __future__ import annotations

import ast
import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from canon.legacy.decision_path_map import FindingSeverity, LegacyCanonConfig


@dataclass(frozen=True)
class DuplicateFragment:
    relpath: str
    lineno: int
    kind: str
    name: str
    semantic_hash: str


@dataclass(frozen=True)
class DuplicateCluster:
    kind: str
    name: str
    semantic_hash: str
    fragments: tuple[DuplicateFragment, ...]
    severity: FindingSeverity
    reason: str


class _SemanticNormalizer(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.AST:
        return ast.copy_location(ast.Name(id="__id__", ctx=node.ctx), node)

    def visit_arg(self, node: ast.arg) -> ast.AST:
        return ast.copy_location(ast.arg(arg="__arg__", annotation=None, type_comment=None), node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        value = self.visit(node.value)
        return ast.copy_location(ast.Attribute(value=value, attr="__attr__", ctx=node.ctx), node)

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, str):
            return ast.copy_location(ast.Constant(value="__str__"), node)
        if isinstance(node.value, (int, float, complex)):
            return ast.copy_location(ast.Constant(value=0), node)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node = self.generic_visit(node)
        node.name = "__fn__"
        node.decorator_list = []
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        node = self.generic_visit(node)
        node.name = "__fn__"
        node.decorator_list = []
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node = self.generic_visit(node)
        node.name = "__class__"
        node.decorator_list = []
        return node


def _iter_python_files(config: LegacyCanonConfig) -> Iterable[Path]:
    for path in config.repo_root.rglob("*.py"):
        relpath = config.normalize_relpath(path)
        if config.is_included_relpath(relpath):
            yield path


def _name_is_interesting(config: LegacyCanonConfig, name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in config.duplicate_logic_name_hints)


def _statement_weight(body: list[ast.stmt]) -> int:
    return sum(1 for stmt in body if not isinstance(stmt, ast.Pass))


def _is_exception_like_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id.endswith(("Error", "Exception", "Warning")):
            return True
        if isinstance(base, ast.Attribute) and base.attr.endswith(("Error", "Exception", "Warning")):
            return True
    return node.name.endswith(("Error", "Exception", "Warning"))


def _is_enum_like_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id.endswith(("Enum", "StrEnum", "IntEnum")):
            return True
        if isinstance(base, ast.Attribute) and base.attr.endswith(("Enum", "StrEnum", "IntEnum")):
            return True
    return False


def _class_method_weight(node: ast.ClassDef) -> int:
    return sum(
        _statement_weight(item.body)
        for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def _semantic_hash(node: ast.AST) -> str:
    normalized = _SemanticNormalizer().visit(copy.deepcopy(ast.fix_missing_locations(node)))
    dumped = ast.dump(normalized, annotate_fields=False, include_attributes=False)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def _classify_severity(config: LegacyCanonConfig, fragments: list[DuplicateFragment]) -> tuple[FindingSeverity, str]:
    paths = {fragment.relpath for fragment in fragments}
    if len(paths) < 2:
        return FindingSeverity.MINOR, "same file duplicate is not treated as cross-surface second brain"
    if any(config.is_decision_surface(path) for path in paths):
        return FindingSeverity.CRITICAL, "semantic duplicate crosses canonical decision/governance surfaces"
    return FindingSeverity.MAJOR, "semantic duplicate exists across multiple business code surfaces"


def scan_duplicate_logic(config: LegacyCanonConfig) -> tuple[DuplicateCluster, ...]:
    buckets: dict[tuple[str, str], list[DuplicateFragment]] = {}

    for path in _iter_python_files(config):
        relpath = config.normalize_relpath(path)
        source = path.read_text(encoding="utf-8")
        lowered_source = source.lower()
        if not any(token in lowered_source for token in config.duplicate_logic_name_hints):
            continue
        tree = ast.parse(source, filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not _name_is_interesting(config, node.name):
                    continue
                if _statement_weight(node.body) < 3:
                    continue
                semantic_hash = _semantic_hash(node)
                buckets.setdefault(("function", semantic_hash), []).append(
                    DuplicateFragment(
                        relpath=relpath,
                        lineno=node.lineno,
                        kind="function",
                        name=node.name,
                        semantic_hash=semantic_hash,
                    )
                )
            elif isinstance(node, ast.ClassDef):
                if not _name_is_interesting(config, node.name):
                    continue
                if _is_exception_like_class(node) or _is_enum_like_class(node):
                    continue
                if _class_method_weight(node) < 4:
                    continue
                semantic_hash = _semantic_hash(node)
                buckets.setdefault(("class", semantic_hash), []).append(
                    DuplicateFragment(
                        relpath=relpath,
                        lineno=node.lineno,
                        kind="class",
                        name=node.name,
                        semantic_hash=semantic_hash,
                    )
                )

    clusters: list[DuplicateCluster] = []
    for (kind, semantic_hash), fragments in buckets.items():
        unique_paths = {item.relpath for item in fragments}
        if len(unique_paths) < 2:
            continue
        ordered = sorted(fragments, key=lambda item: (item.relpath, item.lineno, item.name))
        severity, reason = _classify_severity(config, ordered)
        clusters.append(
            DuplicateCluster(
                kind=kind,
                name=ordered[0].name,
                semantic_hash=semantic_hash,
                fragments=tuple(ordered),
                severity=severity,
                reason=reason,
            )
        )

    return tuple(sorted(clusters, key=lambda item: (item.severity.value, item.kind, item.name, item.semantic_hash)))


__all__ = [
    "DuplicateFragment",
    "DuplicateCluster",
    "scan_duplicate_logic",
]
