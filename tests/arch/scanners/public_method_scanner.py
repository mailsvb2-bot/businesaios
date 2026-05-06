from __future__ import annotations

import ast


def count_public_methods(text: str) -> dict[str, int]:
    tree = ast.parse(text)
    counts: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            count = 0
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                    count += 1
            counts[node.name] = count
    return counts
