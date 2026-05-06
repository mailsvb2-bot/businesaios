from interfaces.web.debug.messaging_policy_snapshot.route_bundle import parse_snapshot_query


def test_parse_snapshot_query_normalizes_defaults() -> None:
    q = parse_snapshot_query(
        tenant_id=None,
        user_id=" u1 ",
        correlation_id=" c1 ",
    )
    assert q.tenant_id == "default"
    assert q.user_id == "u1"
    assert q.correlation_id == "c1"


def test_parse_snapshot_query_normalizes_whitespace_tenant() -> None:
    whitespace_tenant = "   "
    q = parse_snapshot_query(
        tenant_id=whitespace_tenant,
        user_id="u1",
        correlation_id="c1",
    )
    assert q.tenant_id == "default"
