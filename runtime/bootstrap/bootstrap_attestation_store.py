from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from runtime.bootstrap.bootstrap_contract import BootstrapAttestation, BootstrapEnvironment

def _journal_path(env: BootstrapEnvironment) -> Path:
    return env.runtime_dir / "bootstrap" / "attestation_journal.jsonl"

def persist_bootstrap_attestation(
    *,
    env: BootstrapEnvironment,
    attestation: BootstrapAttestation,
) -> Path | None:
    path = _journal_path(env)
    payload = asdict(attestation)
    payload["created_at"] = attestation.created_at.isoformat()
    payload["mode"] = attestation.mode.value
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    except OSError:
        return None
    return path
