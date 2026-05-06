from runtime.boot.web.messaging_policy_service_graph import build_messaging_policy_alert_service
from runtime.boot.web.messaging_policy_service_graph import build_messaging_policy_dashboard_service
from runtime.boot.web.messaging_policy_service_graph import build_messaging_policy_service_graph
from runtime.boot.web.messaging_policy_service_graph import build_messaging_policy_trace_search_service
from runtime.messaging_policy_events.inmemory_event_store import InMemoryMessagingPolicyEventStore


def test_messaging_policy_service_graph_small_builders_align():
    event_store = InMemoryMessagingPolicyEventStore()
    trace = build_messaging_policy_trace_search_service(event_store=event_store)
    dashboard = build_messaging_policy_dashboard_service(trace_search_service=trace)
    alert = build_messaging_policy_alert_service(dashboard_service=dashboard)
    graph = build_messaging_policy_service_graph(event_store=event_store)

    assert type(graph.trace_search_service) is type(trace)
    assert type(graph.dashboard_service) is type(dashboard)
    assert type(graph.alert_service) is type(alert)
