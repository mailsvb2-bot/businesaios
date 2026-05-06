from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_runtime_governance_modules_use_public_surface() -> None:
    targets = {
        "runtime/handlers/governance_build.py": [
            "from runtime.governance import AuditRecord, build_audit_record",
        ],
        "runtime/handlers/governance_evaluate.py": [
            "from runtime.governance import AuditRecord, build_restriction_proposal",
        ],
        "runtime/handlers/governance_explain.py": [
            "from runtime.governance import AuditRecord, explain_decision_audit",
        ],
        "runtime/boot/governance/governance_builder.py": [
            "from runtime.governance import PolicyState",
        ],
        "runtime/boot/governance/governance_registration.py": [
            "from runtime.governance import PolicyState",
        ],
        "runtime/handlers/ads_rl_suggest.py": [
            "from runtime.governance import ProfitMetricsService, PolicyUpdateGate, PolicyUpdateGateError",
        ],
        "runtime/handlers/ads_rl_train_tick.py": [
            "from runtime.governance import ProfitMetricsService",
        ],
    }
    forbidden = [
        "from core.governance.",
        "import core.governance.",
    ]
    for path, expected in targets.items():
        text = _read(path)
        for needle in expected:
            assert needle in text, path
        for needle in forbidden:
            assert needle not in text, path
