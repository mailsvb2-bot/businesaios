from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tools.decision_authority_indirect_scanner import _scan_ast, scan


def _findings(source: str, rel: str = "application/feature/service.py"):
    return _scan_ast(rel=rel, tree=ast.parse(source, filename=rel))


@pytest.mark.parametrize(
    "source",
    [
        "def run(decision_core, state):\n"
        "    return decision_core.decide(state)\n",
        "def run(registry, state):\n"
        "    return registry.get('decision').issue(state)\n",
        "from hidden import decide as choose\n",
        "def bind(decision_core):\n"
        "    return decision_core.decide\n",
        "def bind(decision_core):\n"
        "    return getattr(decision_core, 'decide')\n",
        "def bind(decision_core, method):\n"
        "    return getattr(decision_core, method)\n",
        "def bind(decision_core):\n"
        "    return decision_core.__getattribute__('decide')\n",
        "def bind(decision_core):\n"
        "    return object.__getattribute__(decision_core, 'decide')\n",
        "from builtins import getattr as fetch\n"
        "def bind(decision_core):\n"
        "    return fetch(decision_core, 'decide')\n",
        "import inspect as ins\n"
        "def bind(decision_core):\n"
        "    return ins.getattr_static(decision_core, 'decide')\n",
        "from operator import attrgetter as ag\n"
        "def bind(decision_core):\n"
        "    return ag('decide')(decision_core)\n",
        "import operator as op\n"
        "def bind(decision_core):\n"
        "    return op.methodcaller('issue')(decision_core)\n",
        "def replace(decision_core, replacement):\n"
        "    setattr(decision_core, 'decide', replacement)\n",
        "def replace(decision_core, method, replacement):\n"
        "    setattr(decision_core, method, replacement)\n",
        "def bind(decision_core):\n"
        "    return vars(decision_core)['decide']\n",
        "def bind(decision_core):\n"
        "    return decision_core.__dict__.get('decide')\n",
    ],
)
def test_indirect_authority_paths_are_blocked(source: str) -> None:
    assert _findings(source), source


@pytest.mark.parametrize(
    "source",
    [
        "def create(certificate_service, payload):\n"
        "    return certificate_service.issue(payload)\n",
        "def bind(certificate_service):\n"
        "    return getattr(certificate_service, 'issue')\n",
        "def tune(optimizer, state):\n"
        "    return optimizer.optimize(state)\n",
        "from math_tools import optimize\n"
        "def tune(state):\n"
        "    return optimize(state)\n",
        "from operator import attrgetter\n"
        "def bind(certificate):\n"
        "    return attrgetter('issue')(certificate)\n",
    ],
)
def test_generic_non_decision_services_remain_allowed(source: str) -> None:
    assert _findings(source) == []


def test_exact_canonical_owner_is_allowed() -> None:
    source = (
        "def run(decision_core, state):\n"
        "    return decision_core.decide(state)\n"
    )
    assert _findings(source, "core/ai/decision_core.py") == []


def test_new_file_inside_core_ai_is_not_an_owner() -> None:
    source = (
        "def run(decision_core, state):\n"
        "    return decision_core.decide(state)\n"
    )
    assert _findings(source, "core/ai/shadow_runtime.py")


def test_nested_product_data_directory_is_scanned(tmp_path: Path) -> None:
    path = tmp_path / "product" / "data" / "service.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "def run(decision_core, state):\n"
        "    return decision_core.decide(state)\n",
        encoding="utf-8",
    )
    assert [item.path for item in scan(tmp_path)] == [
        "product/data/service.py"
    ]


def test_root_mutable_data_directory_is_pruned(tmp_path: Path) -> None:
    path = tmp_path / "data" / "state.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "def run(decision_core, state):\n"
        "    return decision_core.decide(state)\n",
        encoding="utf-8",
    )
    assert scan(tmp_path) == ()
