from __future__ import annotations

from pathlib import Path

import pytest

import execution.economic_audit_bundle as module
from execution.economic_audit_bundle import EconomicAuditBundleService


class _RecordingQuarantineSink:
    def __init__(self) -> None:
        self.records: list[object] = []

    def record(self, record: object) -> None:
        self.records.append(record)


def test_recursive_json_failure_is_quarantined_and_reraised(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_path = tmp_path / 'recursive.json'
    bundle_path.write_text('{"payload": {}}', encoding='utf-8')
    sink = _RecordingQuarantineSink()
    service = EconomicAuditBundleService(quarantine_sink=sink)

    def _raise_recursion_error(_: str) -> object:
        raise RecursionError('maximum JSON nesting exceeded')

    monkeypatch.setattr(module.json, 'loads', _raise_recursion_error)

    with pytest.raises(RecursionError, match='maximum JSON nesting exceeded'):
        service.import_json(path=bundle_path)

    assert len(sink.records) == 1
    record = sink.records[0]
    payload = record.to_dict() if hasattr(record, 'to_dict') else dict(record)  # type: ignore[arg-type]
    assert payload['reason'] == 'economic_bundle_parse_failed'
