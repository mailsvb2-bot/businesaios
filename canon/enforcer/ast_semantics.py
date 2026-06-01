from __future__ import annotations

import ast
import re


def full_attr_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = full_attr_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return full_attr_name(node.func)
    return ""


def is_stub_function(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    body = list(node.body)
    if not body:
        return True
    if len(body) == 1 and isinstance(body[0], ast.Pass):
        return True
    return len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str)


def returns_literal_status_ok(node: ast.AST) -> bool:
    if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Dict):
        return False
    pairs = {}
    for k, v in zip(node.value.keys, node.value.values, strict=False):
        if isinstance(k, ast.Constant) and isinstance(k.value, str) and isinstance(v, ast.Constant):
            pairs[k.value] = v.value
    return pairs.get("status") == "ok"


def returns_literal_true(node: ast.AST) -> bool:
    return isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) and node.value.value is True


def looks_like_integration_stub(fn: ast.AST) -> bool:
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    if is_stub_function(fn):
        return True
    if len(fn.body) == 1 and (returns_literal_status_ok(fn.body[0]) or returns_literal_true(fn.body[0])):
        name = fn.name.lower()
        suspicious = ("send", "publish", "apply", "deliver", "route", "dispatch", "heal", "connect")
        return any(key in name for key in suspicious)
    return False


def infra_name_regex() -> re.Pattern[str]:
    return re.compile(r"(?:^|[._])(connector|client|provider)(?:$|[._])")
