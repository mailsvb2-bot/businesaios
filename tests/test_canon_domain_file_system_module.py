from __future__ import annotations

from pathlib import Path

from canon.domain_fs import (
    CANON_DOMAIN_MARKER,
    findings_as_dicts,
    scan_boot_wiring_only,
    scan_canon_domain_file_system,
    scan_thin_runtime_handlers,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_canon_domain_file_system_accepts_compliant_domain(tmp_path: Path) -> None:
    root = tmp_path
    domain = root / "core" / "world_model"
    _write(domain / CANON_DOMAIN_MARKER, 'CANON_DOMAIN_VERSION = "DFS-V1"\n')
    _write(domain / "__init__.py", "")
    _write(domain / "contracts.py", "from __future__ import annotations\n")
    _write(domain / "types.py", "from __future__ import annotations\n")
    _write(domain / "errors.py", "from __future__ import annotations\n")
    _write(domain / "service.py", "from __future__ import annotations\n")
    _write(domain / "guard.py", "from __future__ import annotations\n")
    _write(domain / "builders" / "world_snapshot_builder.py", "from __future__ import annotations\n")
    _write(domain / "evaluators" / "confidence_evaluator.py", "from __future__ import annotations\n")
    findings = scan_canon_domain_file_system(root)
    assert findings == []


def test_scan_canon_domain_file_system_rejects_bad_roles(tmp_path: Path) -> None:
    root = tmp_path
    domain = root / "core" / "simulation"
    _write(domain / CANON_DOMAIN_MARKER, 'CANON_DOMAIN_VERSION = "DFS-V1"\n')
    _write(domain / "contracts.py", "from __future__ import annotations\n")
    _write(domain / "types.py", "from __future__ import annotations\n")
    _write(domain / "errors.py", "from __future__ import annotations\n")
    _write(domain / "service.py", "from __future__ import annotations\n")
    _write(domain / "guard.py", "from __future__ import annotations\n")
    _write(domain / "brain_engine.py", "DecisionRoute(\n")

    findings = scan_canon_domain_file_system(root)
    assert findings
    assert any(i.kind in {"unexpected-domain-root-file", "forbidden-role-name", "second-brain-path-detected"} for i in findings)


def test_scan_thin_runtime_handlers_rejects_decision_logic(tmp_path: Path) -> None:
    root = tmp_path
    path = root / "runtime" / "handlers" / "world_model_build.py"
    _write(
        path,
        "CANON_THIN_HANDLER = True\n\n"
        "def decide() -> None:\n"
        "    return None\n",
    )
    findings = scan_thin_runtime_handlers(root)
    assert any(i.kind == "decision-logic-inside-thin-handler" for i in findings)


def test_scan_boot_wiring_only_rejects_side_effects(tmp_path: Path) -> None:
    root = tmp_path
    path = root / "runtime" / "boot" / "world_model_boot.py"
    _write(
        path,
        "CANON_BOOT_WIRING_ONLY = True\n\n"
        "import requests\n\n"
        "def wire() -> None:\n"
        "    requests.get('https://example.com')\n",
    )
    findings = scan_boot_wiring_only(root)
    assert any(i.kind == "boot-not-wiring-only" for i in findings)


def test_findings_as_dicts_smoke(tmp_path: Path) -> None:
    root = tmp_path
    domain = root / "core" / "knowledge"
    _write(domain / CANON_DOMAIN_MARKER, 'CANON_DOMAIN_VERSION = "DFS-V1"\n')
    findings = scan_canon_domain_file_system(root)
    items = findings_as_dicts(findings)
    assert isinstance(items, list)
