from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from execution.canonical_scenario_governance import canonical_scenario_catalog_entry

CANON_SCENARIO_BASELINE_CATALOG = True

@dataclass
class FileScenarioBaselineCatalog:
    root_dir: Path

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def put(self, *, scenario: str, baseline_name: str, source_run_id: str, metadata: dict[str, Any] | None = None) -> Path:
        target = self.root_dir / f"{self._safe_name(scenario)}.json"
        existing = {}
        if target.exists():
            try:
                existing = json.loads(target.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, OSError):
                existing = {}
        payload = canonical_scenario_catalog_entry(
            scenario=str(scenario),
            baseline_name=str(baseline_name),
            source_run_id=str(source_run_id),
            metadata=dict(metadata or {}),
            existing_payload=existing,
        )
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
        return target

    def get(self, *, scenario: str) -> dict[str, Any]:
        target = self.root_dir / f"{self._safe_name(scenario)}.json"
        payload = json.loads(target.read_text(encoding='utf-8'))
        return canonical_scenario_catalog_entry(
            scenario=str(payload.get('scenario') or scenario),
            baseline_name=str(payload.get('baseline_name') or ''),
            source_run_id=str(payload.get('source_run_id') or ''),
            metadata=dict(payload.get('metadata') or {}),
            existing_payload=payload,
        )

    def exists(self, *, scenario: str) -> bool:
        return (self.root_dir / f"{self._safe_name(scenario)}.json").exists()

    def list_entries(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.root_dir.glob('*.json')):
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
                rows.append(canonical_scenario_catalog_entry(
                    scenario=str(payload.get('scenario') or ''),
                    baseline_name=str(payload.get('baseline_name') or ''),
                    source_run_id=str(payload.get('source_run_id') or ''),
                    metadata=dict(payload.get('metadata') or {}),
                    existing_payload=payload,
                ))
            except (json.JSONDecodeError, OSError):
                continue
        return rows

    @staticmethod
    def _safe_name(value: str) -> str:
        return str(value or '').strip().lower().replace(' ', '_').replace('/', '_')

__all__ = ['CANON_SCENARIO_BASELINE_CATALOG', 'FileScenarioBaselineCatalog']
