from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

CANON_PLATFORM_CONTROL_CENTER_SUPPORT = True

BLOCK_EXCLUDE = {
    '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.git', 'data', 'artifacts', 'assets', 'node_modules'
}
SUSPICIOUS_NAME_HINTS = ('legacy', 'compat', 'shim', 'wrapper', 'public_api', 'catalog')
SEVERITY_ORDER = {'critical': 0, 'major': 1, 'minor': 2}


@dataclass(frozen=True)
class RiskRecommendation:
    file_path: str
    severity: str
    risk_type: str
    summary: str
    recommended_change: str
    change_target: str
    possible_conflict: str | None = None
    line_hint: int | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            'file_path': self.file_path,
            'severity': self.severity,
            'risk_type': self.risk_type,
            'summary': self.summary,
            'recommended_change': self.recommended_change,
            'change_target': self.change_target,
            'possible_conflict': self.possible_conflict,
            'code_navigation': code_navigation_payload(self.file_path, self.line_hint),
            'architectural_score': architectural_score(self.severity, self.risk_type),
            'stop_condition': stop_condition_text(self.risk_type),
        }
        if self.line_hint is not None:
            payload['line_hint'] = self.line_hint
        return payload


def patch_shape_for(risk: RiskRecommendation) -> str:
    if risk.risk_type == 'god_module_pressure':
        return 'Split into contract.py, runtime_support.py, persistence.py, and thin boundary route/page file.'
    if risk.risk_type == 'large_module':
        return 'Extract helper module and leave only orchestration or owner contract in the existing file.'
    if risk.risk_type in {'surface_spread', 'public_api_spread'}:
        return 'Keep one canonical export and reduce wrappers/aliases to compat-only shims.'
    if risk.risk_type == 'legacy_pressure':
        return 'Collapse legacy wrappers and preserve one semantic owner surface with explicit admin visibility.'
    return 'Apply narrow owner-shaped patch and reflect final status/risk in admin plane.'


def patch_template_for(risk: RiskRecommendation) -> str:
    target = risk.change_target
    return (
        f"# patch target: {risk.file_path}\n"
        f"# intent: {risk.recommended_change}\n"
        f"# expected target: {target}\n"
        "1. extract shared logic into a dedicated owner module\n"
        "2. keep the current file as thin orchestration/boundary surface\n"
        "3. remove duplicate wrappers and update admin visibility\n"
    )


def patch_code_for(risk: RiskRecommendation) -> str:
    stem = Path(risk.file_path).stem.replace('-', '_').replace('.', '_') or 'owner_surface'
    type_name = stem.title().replace('_', '')
    if risk.risk_type == 'god_module_pressure':
        return (
            f"# concrete patch suggestion for {risk.file_path}\n"
            f"from dataclasses import dataclass\n\n"
            f"@dataclass(frozen=True, slots=True)\n"
            f"class {type_name}Contract:\n"
            f"    owner_id: str\n\n"
            f"def build_{stem}_service(contract: {type_name}Contract):\n"
            f"    return {{'owner_id': contract.owner_id}}\n"
        )
    if risk.risk_type in {'large_module', 'legacy_pressure'}:
        return (
            f"# concrete patch suggestion for {risk.file_path}\n"
            f"def normalize_{stem}_input(payload: dict) -> dict:\n"
            f"    return dict(payload or {{}})\n\n"
            f"def run_{stem}_owner(payload: dict) -> dict:\n"
            f"    normalized = normalize_{stem}_input(payload)\n"
            f"    return {{'status': 'ok', 'payload': normalized}}\n"
        )
    return (
        f"# concrete patch suggestion for {risk.file_path}\n"
        f"def canonical_{stem}_surface(value):\n"
        f"    return value\n"
    )


def code_navigation_payload(file_path: str, line_hint: int | None) -> dict[str, Any]:
    normalized = str(file_path).strip()
    return {
        'file_path': normalized,
        'line_hint': int(line_hint or 1),
        'editor_hint': f'{normalized}:{int(line_hint or 1)}',
    }


def architectural_score(severity: str, risk_type: str) -> int:
    base = {'critical': 25, 'major': 15, 'minor': 8}.get(str(severity), 5)
    if risk_type in {'god_module_pressure', 'legacy_pressure'}:
        base += 10
    if risk_type in {'surface_spread', 'public_api_spread'}:
        base += 2
    return max(1, min(100, 100 - base))


def stop_condition_text(risk_type: str) -> str:
    if risk_type == 'god_module_pressure':
        return 'File is split into owner-shaped modules and no replacement module exceeds the size threshold.'
    if risk_type == 'large_module':
        return 'Remaining file only contains orchestration or owner contract logic.'
    if risk_type in {'surface_spread', 'public_api_spread'}:
        return 'One canonical export remains and wrappers are compat-only or removed.'
    if risk_type == 'legacy_pressure':
        return 'Legacy wrappers are collapsed and ownership is explicit.'
    return 'Risk row disappears or is downgraded after canonical refactor.'


def now_text() -> str:
    return datetime.now(UTC).isoformat()
