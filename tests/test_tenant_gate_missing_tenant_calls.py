from __future__ import annotations

from pathlib import Path


def test_tenant_gate_no_missing_tenant_calls() -> None:
    """Gate test: forbids legacy call shapes that silently drop tenant_id.

    This prevents regressions where someone reintroduces iter_events() without tenant_id,
    or calls store.append_event() directly bypassing EventLog tenant scoping.
    """
    repo_root = Path(__file__).resolve().parents[1]
    from scripts.audit_tenant_usage import audit

    rc = audit(str(repo_root))
    assert rc == 0, "Tenant usage audit failed. Run: python scripts/audit_tenant_usage.py --root ."
