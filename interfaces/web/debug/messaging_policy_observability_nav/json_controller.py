from __future__ import annotations

from interfaces.web.debug.common.http_response import HttpResponse
from interfaces.web.debug.messaging_policy_observability_nav.page_presenter import page_to_dict, present_page


class MessagingPolicyObservabilityNavJsonController:
    def get_page(self, *, tenant_id) -> HttpResponse:
        body = page_to_dict(present_page(tenant_id=tenant_id))
        return HttpResponse(status_code=200, content_type='application/json', body=body)
