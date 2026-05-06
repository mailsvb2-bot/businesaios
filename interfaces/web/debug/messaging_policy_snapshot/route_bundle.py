from __future__ import annotations

from interfaces.web.debug.messaging_policy_snapshot.api_service import MessagingPolicySnapshotAPIService
from interfaces.web.debug.messaging_policy_snapshot.html_controller import MessagingPolicySnapshotHtmlController
from interfaces.web.debug.messaging_policy_snapshot.json_controller import MessagingPolicySnapshotJsonController
from interfaces.web.debug.messaging_policy_snapshot.query_parser import parse_snapshot_query


class MessagingPolicySnapshotRouteBundle:
    def __init__(self, *, read_service):
        api_service = MessagingPolicySnapshotAPIService(read_service=read_service)
        self._json = MessagingPolicySnapshotJsonController(api_service=api_service)
        self._html = MessagingPolicySnapshotHtmlController(api_service=api_service)

    def json(self, *, tenant_id, user_id, correlation_id):
        query = parse_snapshot_query(tenant_id=tenant_id, user_id=user_id, correlation_id=correlation_id)
        return self._json.get_snapshot(tenant_id=query.tenant_id, user_id=query.user_id, correlation_id=query.correlation_id)

    def html(self, *, tenant_id, user_id, correlation_id):
        query = parse_snapshot_query(tenant_id=tenant_id, user_id=user_id, correlation_id=correlation_id)
        return self._html.get_snapshot_page(tenant_id=query.tenant_id, user_id=query.user_id, correlation_id=query.correlation_id)
