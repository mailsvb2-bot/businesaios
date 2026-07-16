from __future__ import annotations

import ast

from tools.decision_authority_indirect_scanner import _scan_ast


def _findings(source: str):
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
