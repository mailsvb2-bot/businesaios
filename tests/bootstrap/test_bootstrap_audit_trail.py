from __future__ import annotations

import json

from runtime.bootstrap.bootstrap_audit_trail import (
    append_bootstrap_audit_event,
    build_bootstrap_audit_event,
)
from runtime.bootstrap.bootstrap_contract import BootstrapEnvironment, BootstrapMode, BootstrapStatus


def test_append_bootstrap_audit_event_writes_machine_readable_jsonl(tmp_path):
    env = BootstrapEnvironment(
        mode=BootstrapMode.TEST,
        project_root=tmp_path,
        runtime_dir=tmp_path / ".runtime",
        release_manifest_path=tmp_path / "manifest.json",
        strict=False,
        release_attestation_required=False,
        singleton_lock_enabled=False,
    )

    event = build_bootstrap_audit_event(
        status=BootstrapStatus.FAILED,
        code="BOOTSTRAP_FAILED",
        message="synthetic failure",
        details={"attempt": "1"},
    )

    path = append_bootstrap_audit_event(env=env, event=event)
    payload = json.loads(path.read_text(encoding="utf-8").strip())

    assert payload["status"] == "failed"
    assert payload["code"] == "BOOTSTRAP_FAILED"
    assert payload["details"]["attempt"] == "1"
