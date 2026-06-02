from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from application.admin.platform_control_center.support import SEVERITY_ORDER, code_navigation_payload
from runtime.business_autonomy.platform_admin_snapshot_store import FilePlatformAdminSnapshotStore

CANON_PLATFORM_CONTROL_CENTER_SNAPSHOT_DIFF_SERVICE = True


@dataclass(frozen=True)
class SnapshotDiffService:
    def build_risk_diff(self, *, previous_snapshot: Mapping[str, Any] | None, current_snapshot: Mapping[str, Any]) -> dict[str, Any]:
        if previous_snapshot is None:
            return {
                'snapshot_available': False,
                'previous_captured_at_utc': None,
                'current_captured_at_utc': current_snapshot['captured_at_utc'],
                'new_risks': list(current_snapshot.get('risk_rows') or []),
                'resolved_risks': [],
                'changed_severity': [],
                'code_diff_rows': [],
            }
        prev_rows = {(str(item.get('file_path')), str(item.get('risk_type'))): dict(item) for item in list(previous_snapshot.get('risk_rows') or [])}
        curr_rows = {(str(item.get('file_path')), str(item.get('risk_type'))): dict(item) for item in list(current_snapshot.get('risk_rows') or [])}
        new_risks = [curr_rows[key] for key in curr_rows.keys() - prev_rows.keys()]
        resolved = [prev_rows[key] for key in prev_rows.keys() - curr_rows.keys()]
        changed = []
        code_diff_rows = []
        for key in curr_rows.keys() & prev_rows.keys():
            prev_severity = str(prev_rows[key].get('severity') or '')
            curr_severity = str(curr_rows[key].get('severity') or '')
            if prev_severity != curr_severity:
                payload = {
                    'file_path': curr_rows[key].get('file_path'),
                    'risk_type': curr_rows[key].get('risk_type'),
                    'previous_severity': prev_severity,
                    'current_severity': curr_severity,
                    'code_navigation': curr_rows[key].get('code_navigation') or code_navigation_payload(str(curr_rows[key].get('file_path') or ''), curr_rows[key].get('line_hint')),
                }
                changed.append(payload)
                code_diff_rows.append({**payload, 'diff_summary': f'{prev_severity} → {curr_severity}', 'click_action': 'open_editor'})
        return {
            'snapshot_available': True,
            'previous_captured_at_utc': previous_snapshot.get('captured_at_utc'),
            'current_captured_at_utc': current_snapshot['captured_at_utc'],
            'new_risks': sorted(new_risks, key=lambda row: (SEVERITY_ORDER.get(str(row.get('severity')), 9), str(row.get('file_path'))))[:40],
            'resolved_risks': sorted(resolved, key=lambda row: (SEVERITY_ORDER.get(str(row.get('severity')), 9), str(row.get('file_path'))))[:40],
            'changed_severity': sorted(changed, key=lambda row: (SEVERITY_ORDER.get(str(row.get('current_severity')), 9), str(row.get('file_path'))))[:40],
            'code_diff_rows': code_diff_rows[:40],
        }

    def build_trend_rows(self, *, snapshot_store: FilePlatformAdminSnapshotStore, tenant_id: str) -> list[dict[str, Any]]:
        history = list(reversed(snapshot_store.list_history(snapshot_name=f'{tenant_id}:latest', limit=10)))
        rows: list[dict[str, Any]] = []
        for item in history:
            metrics = dict(item.get('trend_metrics') or {})
            rows.append({
                'captured_at_utc': str(item.get('captured_at_utc') or ''),
                'total_risks': int(metrics.get('total_risks') or 0),
                'critical_risks': int(metrics.get('critical_risks') or 0),
                'major_risks': int(metrics.get('major_risks') or 0),
                'minor_risks': int(metrics.get('minor_risks') or 0),
                'connected_businesses': int(metrics.get('connected_businesses') or 0),
            })
        return rows

    def build_block_maturity_trend_rows(self, *, snapshot_store: FilePlatformAdminSnapshotStore, tenant_id: str) -> list[dict[str, Any]]:
        history = list(reversed(snapshot_store.list_history(snapshot_name=f'{tenant_id}:latest', limit=10)))
        per_block: dict[str, list[dict[str, Any]]] = {}
        for item in history:
            captured = str(item.get('captured_at_utc') or '')
            for block_row in list(item.get('block_rows') or []):
                block = str(block_row.get('block') or '').strip()
                if not block:
                    continue
                per_block.setdefault(block, []).append({
                    'captured_at_utc': captured,
                    'risk_score': int(block_row.get('risk_score') or 0),
                    'maturity': str(block_row.get('maturity') or 'unknown'),
                    'python_lines': int(block_row.get('python_lines') or 0),
                })
        rows: list[dict[str, Any]] = []
        for block, history_rows in sorted(per_block.items()):
            latest = history_rows[-1]
            maturity_score = {'strong': 90, 'watch': 65, 'needs_work': 35}.get(latest['maturity'], 50)
            rows.append({
                'block': block,
                'latest_maturity': latest['maturity'],
                'latest_risk_score': latest['risk_score'],
                'maturity_score': maturity_score,
                'history': history_rows,
            })
        return rows[:80]
