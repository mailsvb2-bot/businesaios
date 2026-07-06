from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

CANON_CLIENT_OUTCOME_EXPORT = True


def export_client_outcome_truth_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    normalized_snapshot = dict(snapshot)
    raw = json.dumps(normalized_snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return {
        'snapshot': normalized_snapshot,
        'hash': digest,
        'algorithm': 'sha256',
    }


def verify_client_outcome_truth_export(exported: Mapping[str, Any]) -> bool:
    snapshot = exported.get('snapshot')
    digest = exported.get('hash')
    algorithm = str(exported.get('algorithm') or 'sha256').lower()
    if algorithm != 'sha256' or not isinstance(snapshot, Mapping) or not isinstance(digest, str):
        return False
    expected = export_client_outcome_truth_snapshot(dict(snapshot))
    return expected['hash'] == digest
