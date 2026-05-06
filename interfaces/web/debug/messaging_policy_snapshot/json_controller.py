from __future__ import annotations

from interfaces.web.debug.common.http_response import HttpResponse


def build_not_found_body(*, tenant_id: str, user_id: str, correlation_id: str) -> dict:
    return {
        'ok': False,
        'error': 'SNAPSHOT_NOT_FOUND',
        'tenant_id': str(tenant_id),
        'user_id': str(user_id),
        'correlation_id': str(correlation_id),
    }


class MessagingPolicySnapshotJsonController:
    def __init__(self, *, api_service):
        self._api_service = api_service

    def get_snapshot(self, *, tenant_id: str, user_id: str, correlation_id: str) -> HttpResponse:
        body = self._api_service.get_snapshot(
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=correlation_id,
        )
        if body is None:
            return HttpResponse(
                status_code=404,
                content_type='application/json',
                body=build_not_found_body(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    correlation_id=correlation_id,
                ),
            )
        return HttpResponse(status_code=200, content_type='application/json', body=body)
