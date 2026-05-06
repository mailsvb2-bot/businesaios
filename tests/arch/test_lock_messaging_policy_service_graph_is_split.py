from pathlib import Path


def test_messaging_policy_service_graph_delegates_to_small_builders():
    text = Path('runtime/boot/web/messaging_policy_service_graph.py').read_text(encoding='utf-8')
    assert 'build_messaging_policy_trace_search_service' in text
    assert 'build_messaging_policy_dashboard_service' in text
    assert 'build_messaging_policy_alert_service' in text
    assert 'MessagingPolicyTraceSearchStore' not in text
