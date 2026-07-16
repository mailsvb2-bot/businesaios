from __future__ import annotations

from pathlib import Path


def test_verify_release_shell_isolates_nested_boot_smoke_root() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts" / "verify_release.sh").read_text(encoding="utf-8")

    outer_index = script.index("OUTER_BOOT_SMOKE_ROOT=")
    nested_index = script.index("VERIFY_BOOT_SMOKE_ROOT=")
    export_index = script.index("export BAIOS_BOOT_SMOKE_ROOT=")
    fast_index = script.index("scripts.ci.cli --gate fast")

    assert "BASHPID" in script
    assert "cleanup_verify_boot_smoke" in script
    assert "trap cleanup_verify_boot_smoke EXIT" in script
    assert outer_index < nested_index < export_index < fast_index
