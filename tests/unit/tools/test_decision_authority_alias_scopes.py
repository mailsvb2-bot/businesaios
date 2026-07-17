from __future__ import annotations

import ast

from tools.decision_authority_indirect_scanner import Finding, _scan_ast


def _findings(source: str) -> list[Finding]:
    relative = "application/feature/service.py"
    return _scan_ast(
        rel=relative,
        tree=ast.parse(source, filename=relative),
    )


def test_local_reflection_alias_is_blocked() -> None:
    findings = _findings(
        "def bind(decision_core):\n"
        "    helper = getattr\n"
        "    return helper(decision_core, 'decide')\n"
    )

    assert findings


def test_parameter_shadow_does_not_inherit_module_alias() -> None:
    findings = _findings(
        "from builtins import getattr as helper\n"
        "def safe(helper, certificate):\n"
        "    return helper(certificate, 'issue')\n"
    )

    assert findings == []


def test_alias_does_not_leak_between_functions() -> None:
    findings = _findings(
        "from builtins import getattr as helper\n"
        "def blocked(decision_core):\n"
        "    return helper(decision_core, 'decide')\n"
        "def safe(helper, certificate):\n"
        "    return helper(certificate, 'issue')\n"
    )

    assert len(findings) == 1
    assert findings[0].line == 3


def test_class_local_alias_does_not_leak_into_method() -> None:
    findings = _findings(
        "from builtins import getattr as module_helper\n"
        "class Service:\n"
        "    helper = module_helper\n"
        "    def safe(self, helper, certificate):\n"
        "        return helper(certificate, 'issue')\n"
    )

    assert findings == []


def test_comprehension_target_shadows_reflection_alias() -> None:
    findings = _findings(
        "from builtins import getattr as helper\n"
        "def safe(policies, certificate):\n"
        "    return [\n"
        "        helper(certificate, 'issue')\n"
        "        for helper in policies\n"
        "    ]\n"
    )

    assert findings == []


def test_comprehension_outer_iter_uses_outer_alias() -> None:
    findings = _findings(
        "from builtins import getattr as helper\n"
        "def blocked(decision_core):\n"
        "    return [\n"
        "        item\n"
        "        for item in helper(decision_core, 'decide')\n"
        "    ]\n"
    )

    assert findings


def test_late_module_alias_is_visible_to_function_body() -> None:
    findings = _findings(
        "def blocked(decision_core):\n"
        "    return helper(decision_core, 'decide')\n"
        "from builtins import getattr as helper\n"
    )

    assert findings


def test_late_outer_alias_is_visible_to_nested_function() -> None:
    findings = _findings(
        "def outer(decision_core):\n"
        "    def blocked():\n"
        "        return helper(decision_core, 'decide')\n"
        "    helper = getattr\n"
        "    return blocked()\n"
    )

    assert findings
