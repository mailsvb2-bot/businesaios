from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from application.admin.platform_control_center.support import (
    RiskRecommendation,
    architectural_score,
    code_navigation_payload,
    patch_code_for,
    patch_shape_for,
    patch_template_for,
    stop_condition_text,
)

CANON_PLATFORM_CONTROL_CENTER_REMEDIATION_WORKFLOW_ASSEMBLER = True


@dataclass(frozen=True)
class RemediationWorkflowAssembler:
    repo_root: Path

    def file_meta(self, file_path: str) -> dict[str, Any]:
        target = self.repo_root / file_path
        try:
            text = target.read_text(encoding='utf-8')
        except Exception:
            text = ''
        imports = 0
        if text:
            try:
                tree = ast.parse(text)
            except Exception:
                tree = None
            if tree is not None:
                imports = sum(1 for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))
        python_lines = sum(1 for line in text.splitlines() if line.strip())
        return {'python_lines': python_lines, 'imports': imports}

    @staticmethod
    def owner_guess_for_block(block: str, ownership_rows: Iterable[Mapping[str, Any]]) -> str:
        row = next((item for item in ownership_rows if str(item.get('block')) == block), None)
        if row is None:
            return 'unknown_owner'
        return str(row.get('owner_status') or 'unknown_owner')

    @staticmethod
    def file_architectural_score(*, file_meta: Mapping[str, Any], risks: Iterable[Mapping[str, Any]]) -> int:
        score = 100
        score -= min(25, int(file_meta.get('python_lines') or 0) // 40)
        score -= min(10, int(file_meta.get('imports') or 0))
        for risk in risks:
            score = min(score, int(risk.get('architectural_score') or score))
        return max(1, min(100, score))

    def build_file_passport(self, *, file_path: str, risk_rows: Iterable[Mapping[str, Any]], ownership_rows: Iterable[Mapping[str, Any]], dependency_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        normalized = str(file_path).strip()
        block = normalized.split('/', 1)[0]
        matching_risks = [dict(item) for item in risk_rows if str(item.get('file_path')) == normalized or str(item.get('file_path')) == f'{block}/']
        file_meta = self.file_meta(normalized)
        related_dependencies = [dict(item) for item in dependency_rows if block in {str(item.get('source_block')), str(item.get('target_block'))}][:20]
        score = self.file_architectural_score(file_meta=file_meta, risks=matching_risks)
        return {
            'file_path': normalized,
            'block': block,
            'python_lines': file_meta['python_lines'],
            'imports': file_meta['imports'],
            'owner_guess': self.owner_guess_for_block(block, ownership_rows),
            'risk_rows': matching_risks,
            'architectural_score': score,
            'dependency_context': related_dependencies,
            'recommended_change': matching_risks[0]['recommended_change'] if matching_risks else 'No active risk row. Keep file owner-shaped and admin-visible.',
            'code_navigation': code_navigation_payload(normalized, matching_risks[0].get('line_hint') if matching_risks else 1),
            'passport_cards': {
                'structure': {'python_lines': file_meta['python_lines'], 'imports': file_meta['imports'], 'score': score},
                'ownership': {'block': block, 'owner_guess': self.owner_guess_for_block(block, ownership_rows)},
                'risk_focus': matching_risks[:3],
            },
        }

    def build_remediation_workflow(self, *, file_path: str, risk_rows: Iterable[Mapping[str, Any]], risk_type: str = '') -> dict[str, Any]:
        normalized = str(file_path).strip()
        matching = next(
            (
                item for item in risk_rows
                if str(item.get('file_path')) == normalized and (not risk_type or str(item.get('risk_type')) == str(risk_type).strip())
            ),
            None,
        )
        risk = RiskRecommendation(
            file_path=normalized,
            severity=str((matching or {}).get('severity') or 'major'),
            risk_type=str((matching or {}).get('risk_type') or str(risk_type).strip() or 'manual_remediation'),
            summary=str((matching or {}).get('summary') or 'Manual remediation requested from platform admin.'),
            recommended_change=str((matching or {}).get('recommended_change') or 'Split semantics and keep one thin boundary surface.'),
            change_target=str((matching or {}).get('change_target') or 'owner-shaped module layout'),
            possible_conflict=(matching or {}).get('possible_conflict'),
            line_hint=(matching or {}).get('line_hint') or 1,
        )
        return {
            'file_path': normalized,
            'risk_type': risk.risk_type,
            'workflow_steps': [
                {'order': 1, 'title': 'Open file', 'detail': f'Inspect {normalized} at the hinted line and confirm mixed semantics.'},
                {'order': 2, 'title': 'Split ownership', 'detail': patch_shape_for(risk)},
                {'order': 3, 'title': 'Apply canonical patch', 'detail': patch_template_for(risk)},
                {'order': 4, 'title': 'Reflect in admin', 'detail': 'Update admin visibility and ensure the resulting feature remains observable in /web/platform-admin.'},
                {'order': 5, 'title': 'Verify stop condition', 'detail': stop_condition_text(risk.risk_type)},
            ],
            'patch_template': patch_template_for(risk),
            'patch_code': patch_code_for(risk),
            'code_navigation': code_navigation_payload(normalized, risk.line_hint),
            'next_action': 'apply_patch_then_refresh_admin',
        }

    def build_remediation_run(self, *, file_path: str, risk_rows: Iterable[Mapping[str, Any]], risk_type: str = '') -> dict[str, Any]:
        workflow = self.build_remediation_workflow(file_path=file_path, risk_rows=risk_rows, risk_type=risk_type)
        return {'status': 'prepared', **workflow}
