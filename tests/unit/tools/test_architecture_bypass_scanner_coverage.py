from __future__ import annotations

from pathlib import Path

from tools import architecture_bypass_scanner as scanner


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_finding_format_is_stable() -> None:
    finding = scanner.Finding(
        code="raw_eval_exec",
        path="application/demo.py",
        line=7,
        detail="eval('1')",
    )

    assert finding.format() == "application/demo.py:7: raw_eval_exec: eval('1')"


def test_scan_detects_raw_side_effects_and_dynamic_imports(tmp_path: Path) -> None:
    _write(
        tmp_path / "application/bad.py",
        "import requests\n"
        "def run():\n"
        "    requests.get('https://example.test')\n"
        "    __import__('os')\n"
        "    eval('1 + 1')\n",
    )

    findings = scanner.scan(tmp_path)
    codes = {finding.code for finding in findings}

    assert "raw_side_effect_call_outside_owner" in codes
    assert "dynamic_import_outside_owner" in codes
    assert "raw_eval_exec" in codes


def test_scan_ignores_approved_raw_effect_owner(tmp_path: Path) -> None:
    _write(
        tmp_path / "runtime/_internal/effects_actions/http_action.py",
        "import subprocess\n"
        "def run():\n"
        "    subprocess.run(['true'])\n",
    )

    assert scanner.scan(tmp_path) == ()


def test_scan_detects_text_deny_rules_outside_approved_owners(tmp_path: Path) -> None:
    _write(
        tmp_path / "application/text_rules.py",
        "import subprocess\n"
        "def run():\n"
        "    subprocess.Popen(['true'])\n"
        "    subprocess.run(['true'], shell=True)\n"
        "    return {'verify': False}\n",
    )

    codes = [finding.code for finding in scanner.scan(tmp_path)]

    assert "raw_subprocess_popen" in codes
    assert "unsafe_shell_true" in codes


def test_scan_detects_syntax_error_and_non_utf8_file(tmp_path: Path) -> None:
    _write(tmp_path / "core/bad_syntax.py", "def broken(:\n")
    bad_bytes = tmp_path / "core/non_utf8.py"
    bad_bytes.parent.mkdir(parents=True, exist_ok=True)
    bad_bytes.write_bytes(b"\xff\xfe\x00")

    findings = scanner.scan(tmp_path)
    codes = {finding.code for finding in findings}

    assert "syntax_error" in codes
    assert "non_utf8_python_file" in codes


def test_scan_detects_decision_bypass_outside_owner(tmp_path: Path) -> None:
    _write(
        tmp_path / "application/rogue_decision.py",
        "class Engine:\n"
        "    def run(self, planner):\n"
        "        return planner.decide()\n",
    )

    findings = scanner.scan(tmp_path)

    assert any(finding.code == "possible_decision_core_bypass" for finding in findings)


def test_scan_ignores_scripts_and_test_like_paths(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts/dev_helper.py",
        "import requests\n"
        "def run():\n"
        "    return requests.get('https://example.test')\n",
    )

    assert scanner.scan(tmp_path) == ()


def test_main_returns_success_when_scan_is_clean(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / "application/clean.py", "VALUE = 1\n")

    assert scanner.main() == 0
