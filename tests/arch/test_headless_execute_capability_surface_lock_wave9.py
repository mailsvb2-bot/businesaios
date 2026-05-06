from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_headless_route_handlers_use_canonical_capability_normalizer() -> None:
    text = (ROOT / 'interfaces' / 'api' / 'headless_route_handlers.py').read_text(encoding='utf-8')
    assert 'from execution.capability_operator_view import merge_capability_views, normalize_capability_view' in text
    assert 'capability_view=merge_capability_views(step.payload, step.feedback)' in text
    assert 'capability_view=normalize_capability_view(report.final_feedback)' in text


def test_headless_route_handlers_do_not_parse_capability_fields_manually() -> None:
    text = (ROOT / 'interfaces' / 'api' / 'headless_route_handlers.py').read_text(encoding='utf-8')
    forbidden = ["['capability_diagnostics']", "['execution_verdict']", "['policy_verdict']", "['capability_planning']"]
    for token in forbidden:
        assert token not in text
