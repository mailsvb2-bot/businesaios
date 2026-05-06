import ast

from runtime.security.ast_bypass_guard import _Visitor


def _violations(src: str, rel: str = "x.py"):
    tree = ast.parse(src)
    v = _Visitor(rel)
    v.visit(tree)
    return v.violations


def test_detects_importlib_import_module_runtime_internal():
    src = """
import importlib
m = importlib.import_module('runtime._internal._effects_impl')
"""
    assert _violations(src)


def test_detects_dunder_import_runtime_internal():
    src = """
m = __import__('runtime._internal._effects_impl')
"""
    assert _violations(src)


def test_detects_getattr_internal_bypass():
    src = """
import runtime
x = getattr(runtime, '_internal')
"""
    assert _violations(src)
