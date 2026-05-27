from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

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
                    summary='Block has a high count of compat/legacy surfaces and may hide duplicate ownership.',
                    recommended_change='Audit legacy/compat files in this block, keep one real owner surface, and reduce wrapper proliferation.',
                    change_target='single owner module per semantic surface',
                    possible_conflict='Wrapper drift and public API alias spread can mask real implementation ownership.',
                ))
            if int(row.get('public_api_files', 0) or 0) >= 3:
                risks.append(RiskRecommendation(
                    file_path=f"{row['block']}/",
                    severity='minor',
                    risk_type='public_api_spread',
                    summary='Multiple public_api surfaces in one block can hide canonical ownership.',
                    recommended_change='Keep one explicit package owner export and demote other public_api surfaces to thin aliases or remove them.',
                    change_target='single explicit package export',
                ))
        deduped: dict[tuple[str, str, str], RiskRecommendation] = {}
        for risk in risks:
            key = (risk.file_path, risk.risk_type, risk.summary)
            deduped.setdefault(key, risk)
        ordered = sorted(deduped.values(), key=lambda item: (SEVERITY_ORDER.get(item.severity, 9), item.file_path, item.risk_type))
        return tuple(ordered[:80])

    def build_dependency_rows(self) -> list[dict[str, Any]]:
        counts: dict[tuple[str, str], int] = {}
        candidate_paths: list[Path] = []
        for path in sorted(self.repo_root.iterdir(), key=lambda item: item.name):
            if not path.is_dir() or path.name in BLOCK_EXCLUDE or path.name.startswith('.'):
                continue
            block_files = sorted(path.rglob('*.py'))
            ranked = sorted(
                block_files,
                key=lambda item: (
                    0 if item.name in {'__init__.py', 'public_api.py'} else 1,
                    len(item.parts),
                    item.name,
                ),
            )
            candidate_paths.extend(ranked[:10])
        for path in candidate_paths[:240]:
            rel = path.relative_to(self.repo_root).as_posix()
            block = rel.split('/', 1)[0]
            try:
                tree = ast.parse(path.read_text(encoding='utf-8'))
            except Exception:
                continue
            imported_blocks: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        target = str(alias.name or '').split('.', 1)[0]
                        if target and target != block and (self.repo_root / target).exists():
                            imported_blocks.add(target)
                elif isinstance(node, ast.ImportFrom):
                    target = str(node.module or '').split('.', 1)[0]
                    if target and target != block and (self.repo_root / target).exists():
                        imported_blocks.add(target)
            for target in imported_blocks:
                counts[(block, target)] = counts.get((block, target), 0) + 1
        rows = [
            {
                'source_block': source,
                'target_block': target,
                'import_count': count,
                'edge_kind': 'cross_block_import',
                'graph_mode': 'representative_scan',
            }
            for (source, target), count in counts.items()
        ]
        rows.sort(key=lambda row: (-int(row['import_count']), row['source_block'], row['target_block']))
        return rows[:120]

    def build_conflict_rows(self, *, block_rows: Iterable[Mapping[str, Any]], dependency_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        block_map = {str(row['block']): row for row in block_rows}
        reverse_edges: dict[tuple[str, str], int] = {}
        for edge in dependency_rows:
            reverse_edges[(str(edge['source_block']), str(edge['target_block']))] = int(edge['import_count'])
        rows: list[dict[str, Any]] = []
        for (source, target), count in reverse_edges.items():
            reverse = reverse_edges.get((target, source), 0)
            source_row = block_map.get(source, {})
            target_row = block_map.get(target, {})
            if reverse > 0:
                rows.append({
                    'conflict_kind': 'bidirectional_dependency',
                    'source_block': source,
                    'target_block': target,
                    'summary': 'Blocks import each other and risk ownership ambiguity.',
                    'recommended_change': 'Move shared semantics into one owner block or extract a lower shared primitive.',
                    'possible_conflict': 'Circular dependency or hidden dual ownership.',
                    'score': count + reverse,
                })
            elif int(source_row.get('compat_files', 0) or 0) >= 8 and int(target_row.get('compat_files', 0) or 0) >= 8:
                rows.append({
                    'conflict_kind': 'legacy_overlap',
                    'source_block': source,
                    'target_block': target,
                    'summary': 'Both blocks carry legacy pressure and import relation exists.',
                    'recommended_change': 'Collapse wrappers and keep one explicit semantic owner between the connected blocks.',
                    'possible_conflict': 'Compat surfaces can drift independently and mask true owner.',
                    'score': count,
                })
        rows.sort(key=lambda row: (-int(row['score']), row['source_block'], row['target_block'], row['conflict_kind']))
        unique: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for row in rows:
            a, b = sorted((row['source_block'], row['target_block']))
            key = (a, b, row['conflict_kind'])
            if key in seen:
                continue
            seen.add(key)
            unique.append(row)
        return unique[:60]

    def build_visual_conflict_map(self, *, conflict_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        nodes: set[str] = set()
        edges: list[dict[str, Any]] = []
        for row in list(conflict_rows)[:80]:
            source = str(row['source_block'])
            target = str(row['target_block'])
            nodes.add(source)
            nodes.add(target)
            edges.append({
                'source': source,
                'target': target,
                'kind': str(row['conflict_kind']),
                'weight': int(row.get('score') or 1),
                'summary': str(row.get('summary') or ''),
                'click_endpoint': '/control-plane/admin/platform-ownership-drilldown',
            })
        return {
            'nodes': [{'id': item, 'label': item} for item in sorted(nodes)],
            'edges': edges,
            'render_mode': 'force_graph',
            'legend': {'bidirectional_dependency': 'amber', 'legacy_overlap': 'red'},
        }
