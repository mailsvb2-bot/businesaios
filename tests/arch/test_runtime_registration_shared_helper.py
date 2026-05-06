from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRATIONS_DIR = ROOT / "boot" / "registrations"

ALLOWED_DIRECT_RESULT_IMPORTS = {
    "_shared.py",
    "register_decision_core.py",
    "register_governance.py",
}


def test_registration_modules_reuse_shared_runtime_registration_helper() -> None:
    offenders: list[str] = []
    for path in sorted(REGISTRATIONS_DIR.glob("*.py")):
        if path.name in ALLOWED_DIRECT_RESULT_IMPORTS:
            continue
        text = path.read_text(encoding="utf-8")
        if "from runtime.registration_result import RegistrationResult" in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, (
        "Registration modules should use boot.registrations._shared.register_runtime_service "
        "instead of repeating manual RegistrationResult assembly: " + ", ".join(offenders)
    )
