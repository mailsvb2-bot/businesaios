from __future__ import annotations

from interfaces.web.debug.common.query_utils import clean_text
from interfaces.web.debug.messaging_policy_snapshot.query_model import SnapshotQuery


def parse_snapshot_query(*, tenant_id: object | None, user_id: object | None, correlation_id: object | None) -> SnapshotQuery:
    return SnapshotQuery(
        tenant_id=clean_text(tenant_id, default='default'),
        user_id=clean_text(user_id),
        correlation_id=clean_text(correlation_id),
    )
