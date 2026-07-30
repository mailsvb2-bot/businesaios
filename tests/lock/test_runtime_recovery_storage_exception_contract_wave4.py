from __future__ import annotations

from pathlib import Path


def test_recovery_storage_defaults_are_fail_closed() -> None:
    source = Path("runtime/recovery.py").read_text(encoding="utf-8")
    plan = source[source.index("def _recovery_plan"):source.index("def _warn_recovery_issue")]
    claim = source[source.index("def _ensure_claim_or_skip"):source.index("def _finalize_terminal_skip")]
    enumeration = source[source.index("def _read_outbox_items"):source.index("def _item_tenant_id")]
    terminal = source[source.index("def _finalize_terminal_skip"):source.index("def _plan_action")]

    assert "except Exception" not in plan
    assert "return None if reliability is None else reliability.plan(env)" in plan
    assert enumeration.count("except Exception") == 1
    assert "outbox enumeration boundary" in enumeration
    assert "ownership-read boundary" in claim
    assert "return False" in claim
    assert "current = None" not in claim
    assert "claim boundary" in claim
    assert "except Exception" not in terminal
    assert "finalize_terminal_recovery_outcome(" in terminal
