from __future__ import annotations

import ast
from typing import Set


COMPLEXITY_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.BoolOp,
    ast.IfExp,
    ast.Match,
)


def parse_import_bases(source_text: str) -> Set[str]:
    try:
        tree = ast.parse(source_text)
    except Exception:
        return set()
    bases: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                bases.add((n.name or "").split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            bases.add(node.module.split(".")[0])
    return {b for b in bases if b}


def function_cyclomatic_complexity(fn: ast.AST) -> int:
    c = 1
    for node in ast.walk(fn):
        if isinstance(node, COMPLEXITY_NODES):
            c += 1
    return c


def is_public_name(name: str) -> bool:
    return not name.startswith("_")
