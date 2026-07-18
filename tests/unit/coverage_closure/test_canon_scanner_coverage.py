from __future__ import annotations

import ast
from pathlib import Path

from canon.collapse.decision_path_map import FindingSeverity, LegacyCanonConfig
from canon.collapse.god_module_detector import scan_god_modules
from canon.collapse.hidden_logic_detector import scan_hidden_logic
from canon.collapse.import_cycle_detector import (
    _current_package,
    _existing_module_prefix,
    _module_name,
    _resolve_relative,
    _strongly_connected_components,
    _top_level_import_candidates,
    build_p0_import_cycle_report,
)
from canon.collapse.wrapper_guard import scan_legacy_wrappers


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_legacy_wrapper_guard_detects_every_non_thin_shape(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "runtime/application/compat_wrapper.py",
        '''"""compat"""\nimport os\nVALUE = 1\n\ndef substantial(x):\n    a = x + 1\n    b = a + 1\n    c = b + 1\n    d = c + 1\n    return d\n\ndef not_forwarder():\n    value = 1\n    return value\n\nclass Bad:\n    pass\n\nprint("runtime")\n\nif VALUE:\n    VALUE = 2\n''',
    )
    _write(
        tmp_path,
        "core/decision/public_api.py",
        "from x import y\n\ndef forward(value):\n    return y(value)\n",
    )
    config = LegacyCanonConfig(
        repo_root=tmp_path,
        include_prefixes=("runtime/", "core/"),
        decision_surface_prefixes=("core/decision/",),
        max_thin_wrapper_non_empty_lines=5,
        max_thin_wrapper_function_body_statements=3,
    )
    findings = scan_legacy_wrappers(config)
    reasons = {item.reason for item in findings}
    assert any("size budget" in reason for reason in reasons)
    assert any("substantial body" in reason for reason in reasons)
    assert any("pure forwarder" in reason for reason in reasons)
    assert any("class compatibility" in reason for reason in reasons)
    assert any("runtime call" in reason for reason in reasons)
    assert any("top-level behavior" in reason for reason in reasons)
    assert findings == tuple(sorted(findings, key=lambda item: (item.relpath, item.lineno, item.symbol)))


def test_import_cycle_helpers_and_full_report(tmp_path: Path) -> None:
    init = _write(tmp_path, "pkg/__init__.py", "from . import a\n")
    a = _write(tmp_path, "pkg/a.py", "from . import b\nif TYPE_CHECKING:\n    import ignored\n")
    _write(tmp_path, "pkg/b.py", "import pkg.a\n")
    _write(tmp_path, "pkg/bad.py", "def broken(:\n")
    _write(tmp_path, "tests/ignored.py", "import pkg.a\n")

    assert _module_name(tmp_path, init) == "pkg"
    assert _module_name(tmp_path, a) == "pkg.a"
    assert _current_package(init, "pkg") == "pkg"
    assert _current_package(a, "pkg.a") == "pkg"
    assert _resolve_relative("pkg.sub", 1, "x") == "pkg.sub.x"
    assert _resolve_relative("pkg.sub", 2, None) == "pkg"
    assert _existing_module_prefix("pkg.a.name", {"pkg", "pkg.a"}) == "pkg.a"
    assert _existing_module_prefix("missing", {"pkg"}) is None

    tree = ast.parse("import x.y\nfrom .sub import name\nfrom .sub import *\nif TYPE_CHECKING:\n import hidden\n")
    assert _top_level_import_candidates(a, "pkg.a", tree.body[0]) == ("x.y",)
    rel = _top_level_import_candidates(a, "pkg.a", tree.body[1])
    assert "pkg.sub" in rel and "pkg.sub.name" in rel
    assert _top_level_import_candidates(a, "pkg.a", tree.body[2]) == ("pkg.sub",)
    assert _top_level_import_candidates(a, "pkg.a", tree.body[3]) == ()
    assert _top_level_import_candidates(a, "pkg.a", ast.parse("x = 1").body[0]) == ()

    components = _strongly_connected_components({"a": {"b"}, "b": {"a"}, "self": {"self"}, "c": set()})
    assert ("a", "b") in components and ("self",) in components

    report = build_p0_import_cycle_report(tmp_path)
    assert report.production_python_files == 4
    assert report.modules == 4
    assert report.parse_errors and report.parse_errors[0][0] == "pkg/bad.py"
    assert any({"pkg.a", "pkg.b"} <= set(cycle.modules) for cycle in report.p0_cycles)
    assert report.edges >= 2


def test_god_module_and_hidden_logic_scanners(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "core/ai/large.py",
        "import os\nimport sys\nclass Complex:\n    def a(self):\n        x=1\n        y=2\n        return x+y\n\ndef f1():\n    return 1\n\ndef f2():\n    return 2\n" + "\n".join(f"X{i} = {i}" for i in range(12)),
    )
    _write(tmp_path, "core/ai/critical.py", "\n".join(f"X{i}={i}" for i in range(50)))
    _write(tmp_path, "core/other/large_non_decision.py", "\n".join(f"X{i}={i}" for i in range(15)))
    _write(tmp_path, "tests/allowlisted.py", "\n".join(f"X{i}={i}" for i in range(100)))
    config = LegacyCanonConfig(
        repo_root=tmp_path,
        include_prefixes=("core/", "tests/"),
        decision_surface_prefixes=("core/ai/",),
        god_module_allowlist_prefixes=("tests/",),
        god_module_lines_major=10,
        god_module_lines_critical=40,
        god_module_functions_major=1,
        god_module_functions_critical=3,
        god_module_classes_major=0,
        god_module_classes_critical=3,
        god_module_imports_major=1,
        god_module_imports_critical=5,
    )
    findings = scan_god_modules(config)
    assert any(item.relpath == "core/ai/critical.py" and item.severity is FindingSeverity.CRITICAL for item in findings)
    assert any(item.relpath == "core/ai/large.py" and item.severity is FindingSeverity.MAJOR for item in findings)
    assert all(item.relpath != "core/other/large_non_decision.py" for item in findings)
    assert all(not item.relpath.startswith("tests/") for item in findings)

    _write(
        tmp_path,
        "core/other/hidden.py",
        "class StrategyBrain:\n    pass\n\nclass DecisionEngine:\n    pass\n\ndef decide_strategy():\n    return None\n\ndef decide_offer():\n    return {'selected_action': 'send'}\n\ndef harmless():\n    return {'selected_action': 'ignored'}\n",
    )
    _write(tmp_path, "core/ai/allowed.py", "class StrategyBrain:\n    pass\n")
    hidden = scan_hidden_logic(config)
    symbols = {item.symbol for item in hidden}
    assert {"StrategyBrain", "decide_strategy", "decide_offer"} <= symbols
    assert "harmless" not in symbols
    assert all(item.relpath != "core/ai/allowed.py" for item in hidden)
