from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from application.admin.platform_control_center.support import (
    BLOCK_EXCLUDE,
    SEVERITY_ORDER,
    SUSPICIOUS_NAME_HINTS,
    RiskRecommendation,
)

CANON_PLATFORM_CONTROL_CENTER_RISK_PROJECTION_LAYER = True


@dataclass(frozen=True)
class RiskProjectionLayer:
    repo_root: Path

    def build_block_rows(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        python_files: list[dict[str, Any]] = []
        for path in sorted(self.repo_root.iterdir(), key=lambda item: item.name):
            if not path.is_dir() or path.name in BLOCK_EXCLUDE or path.name.startswith('.'):
                continue
            py_files = list(path.rglob('*.py'))
            if not py_files:
                continue
            python_lines = 0
            public_api_files = 0
            compat_files = 0
            large_files = 0
            for item in py_files:
                try:
                    text = item.read_text(encoding='utf-8')
                except Exception:
                    text = ''
                lines = sum(1 for line in text.splitlines() if line.strip())
                python_lines += lines
                public_api_files += 1 if item.name == 'public_api.py' else 0
                compat_files += 1 if any(token in item.as_posix() for token in ('compat', 'legacy', 'shim', 'wrapper')) else 0
                large_files += 1 if lines >= 450 else 0
                python_files.append({'path': item.relative_to(self.repo_root).as_posix(), 'lines': lines, 'block': path.name, 'name': item.name})
            risk_score = compat_files * 2 + public_api_files + large_files
            maturity = 'strong' if risk_score <= 2 else 'watch' if risk_score <= 5 else 'needs_work'
            rows.append({
                'block': path.name,
                'python_files': len(py_files),
                'python_lines': python_lines,
                'public_api_files': public_api_files,
                'compat_files': compat_files,
                'large_files': large_files,
                'risk_score': risk_score,
                'maturity': maturity,
            })
        return rows, python_files

    def build_risk_recommendations(self, *, block_rows: Iterable[Mapping[str, Any]], python_files: Iterable[Mapping[str, Any]]) -> tuple[RiskRecommendation, ...]:
        risks: list[RiskRecommendation] = []
        for item in sorted(python_files, key=lambda row: (-int(row['lines']), str(row['path'])))[:40]:
            line_hint = 1
            if int(item['lines']) >= 700:
                risks.append(RiskRecommendation(
                    file_path=str(item['path']),
                    severity='critical',
                    risk_type='god_module_pressure',
                    summary='Large file is at risk of becoming a god module or hidden owner surface.',
                    recommended_change='Split the file into owner contracts, persistence/runtime helpers, and thin boundary adapters.',
                    change_target='smaller owner-shaped modules with one responsibility each',
                    possible_conflict='Large modules often accumulate mixed policy/execution/infrastructure semantics.',
                    line_hint=line_hint,
                ))
            elif int(item['lines']) >= 450:
                risks.append(RiskRecommendation(
                    file_path=str(item['path']),
                    severity='major',
                    risk_type='large_module',
                    summary='Module is getting large enough to hide mixed semantics and future regressions.',
                    recommended_change='Extract narrow helper modules and keep only the owner contract / orchestration entry in this file.',
                    change_target='owner contract + thin orchestration surface',
                    line_hint=line_hint,
                ))
            if any(token in str(item['name']) for token in SUSPICIOUS_NAME_HINTS):
                risks.append(RiskRecommendation(
                    file_path=str(item['path']),
                    severity='minor',
                    risk_type='surface_spread',
                    summary='Compat/public wrapper naming suggests boundary spread or alias layering.',
                    recommended_change='Reduce duplicate wrappers and keep one explicit canonical export per semantic surface.',
                    change_target='single canonical export or compat shim only',
                    line_hint=line_hint,
                ))
        for row in block_rows:
            if int(row.get('compat_files', 0) or 0) >= 8:
                risks.append(RiskRecommendation(
                    file_path=f"{row['block']}/",
                    severity='major',
                    risk_type='legacy_pressure',
                    summary='Block contains many compat/legacy/shim surfaces.',
                    recommended_change='Audit aliases and keep only canonical public surfaces plus documented transitional shims.',
                    change_target='compat layer reduction plan',
                ))
            if int(row.get('public_api_files', 0) or 0) >= 2:
                risks.append(RiskRecommendation(
                    file_path=f"{row['block']}/",
                    severity='minor',
                    risk_type='public_api_spread',
                    summary='Multiple public_api.py surfaces may hide duplicate API ownership.',
                    recommended_change='Confirm one canonical public surface and route aliases through it.',
                    change_target='single public API owner per block',
                ))
        return tuple(risks[:120])
