from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from application.admin.platform_control_center.support import (
    RiskRecommendation,
    architectural_score,
    code_navigation_payload,
    patch_code_for,
    patch_shape_for,
    patch_template_for,
    stop_condition_text,
)

CANON_PLATFORM_CONTROL_CENTER_PATCH_SUGGESTION_ENGINE = True


@dataclass(frozen=True)
class PatchSuggestionEngine:
    def build_remediation_rows(self, risks: Iterable[RiskRecommendation]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for risk in risks:
            rows.append({
                'file_path': risk.file_path,
                'severity': risk.severity,
                'risk_type': risk.risk_type,
                'change_summary': risk.recommended_change,
                'change_target': risk.change_target,
                'possible_conflict': risk.possible_conflict,
                'suggested_patch_shape': patch_shape_for(risk),
                'admin_followup': 'Expose resulting status/risk row in /web/platform-admin after implementation.',
                'code_navigation': code_navigation_payload(risk.file_path, risk.line_hint),
                'architectural_score': architectural_score(risk.severity, risk.risk_type),
                'stop_condition': stop_condition_text(risk.risk_type),
            })
        return rows[:80]

    def build_patch_suggestions(self, risks: Iterable[RiskRecommendation]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for risk in risks:
            rows.append({
                'file_path': risk.file_path,
                'risk_type': risk.risk_type,
                'severity': risk.severity,
                'patch_summary': risk.recommended_change,
                'patch_template': patch_template_for(risk),
                'patch_code': patch_code_for(risk),
                'code_navigation': code_navigation_payload(risk.file_path, risk.line_hint),
                'apply_endpoint': '/control-plane/admin/platform-remediation-run',
                'preview_mode': 'inline_patch_code_preview_editor',
            })
        return rows[:80]
