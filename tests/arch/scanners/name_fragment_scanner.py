from __future__ import annotations

import ast


def find_function_names(text: str) -> tuple[str, ...]:
    tree = ast.parse(text)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            names.append(node.name)
    return tuple(sorted(names))


def find_class_names(text: str) -> tuple[str, ...]:
    tree = ast.parse(text)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            names.append(node.name)
    return tuple(sorted(names))
