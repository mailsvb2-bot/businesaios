from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from application.admin.platform_control_center.support import RiskRecommendation

CANON_PLATFORM_CONTROL_CENTER_STOP_CONDITION_VIEW = True


@dataclass(frozen=True)
class StopConditionView:
    def build_stop_conditions(self, *, block_rows: Iterable[Mapping[str, Any]], risks: Iterable[RiskRecommendation]) -> list[dict[str, Any]]:
        risk_counts: dict[str, int] = {}
        critical_counts: dict[str, int] = {}
        for risk in risks:
            block = str(risk.file_path).split('/', 1)[0]
            risk_counts[block] = risk_counts.get(block, 0) + 1
            if risk.severity == 'critical':
                critical_counts[block] = critical_counts.get(block, 0) + 1
        rows: list[dict[str, Any]] = []
        for row in block_rows:
            block = str(row['block'])
            rows.append({
                'block': block,
                'current_maturity': row['maturity'],
                'risk_score': int(row['risk_score']),
                'risk_count': risk_counts.get(block, 0),
                'critical_count': critical_counts.get(block, 0),
                'stop_condition': 'No critical risks, at most 2 residual findings, and one explicit owner export per semantic surface.',
                'progress_percent': max(0, min(100, 100 - int(row['risk_score']) * 8 - critical_counts.get(block, 0) * 12)),
            })
        rows.sort(key=lambda item: (int(item['progress_percent']), item['block']))
        return rows[:80]
