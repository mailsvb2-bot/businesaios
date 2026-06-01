from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_headless_feedback_merges_capability_view_from_action_and_output() -> None:
    text = (ROOT / 'execution' / 'headless_feedback.py').read_text(encoding='utf-8')
    assert 'merge_capability_views(' in text
    assert '_dictish(getattr(result, "output", {}))' in text


def test_admin_route_handlers_use_normalized_capability_view_only() -> None:
    text = (ROOT / 'interfaces' / 'api' / 'admin_route_handlers.py').read_text(encoding='utf-8')
    assert 'normalize_capability_view(capability_view)' in text
