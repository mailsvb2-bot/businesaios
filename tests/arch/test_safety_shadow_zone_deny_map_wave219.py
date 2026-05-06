from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

LEGACY_SAFETY_SHADOW_ZONES: tuple[str, ...] = (
    'runtime/enforcement/',
    'runtime/governance/',
    'runtime/messaging_policy/',
    'runtime/mutation_guards.py',
    'runtime/guard.py',
)

FORBIDDEN_SAFETY_SHADOW_TOKENS: tuple[str, ...] = (
    'SecondDecisionCore',
    'StrategyBrain',
    'emit_final_action',
    'issue_strategy',
    'select_final_action',
)

ALLOWED_COORDINATION_TOKENS: tuple[str, ...] = (
    'build_safety_control_runtime',
    'evaluate_runtime_action_controls',
    'record_execution_outcome',
)


def test_legacy_safety_shadow_zones_do_not_embed_second_brain_tokens() -> None:
    offenders: list[str] = []
    for rel in LEGACY_SAFETY_SHADOW_ZONES:
        path = ROOT / rel
        if path.is_dir():
            candidates = sorted(item for item in path.rglob('*.py') if item.is_file())
        else:
            candidates = [path] if path.exists() else []
        for candidate in candidates:
            text = candidate.read_text(encoding='utf-8')
            if any(token in text for token in ALLOWED_COORDINATION_TOKENS):
                continue
            bad = [token for token in FORBIDDEN_SAFETY_SHADOW_TOKENS if token in text]
            if bad:
                offenders.append(f"{candidate.relative_to(ROOT)} -> {', '.join(bad)}")
    assert not offenders, 'legacy safety shadow-zones contain second-brain tokens:\n' + '\n'.join(offenders)
