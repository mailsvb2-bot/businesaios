from runtime.boot.web.messaging_policy_service_graph import build_messaging_policy_service_graph
from runtime.messaging_policy_events.inmemory_event_store import InMemoryMessagingPolicyEventStore


def test_service_graph_builds_single_stack() -> None:
    graph = build_messaging_policy_service_graph(
        event_store=InMemoryMessagingPolicyEventStore(),
    )
    assert graph.trace_search_service is not None
    assert graph.dashboard_service is not None
    assert graph.alert_service is not None
