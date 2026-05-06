from __future__ import annotations

from interfaces.web.debug.messaging_policy_observability_nav.html_controller import MessagingPolicyObservabilityNavHtmlController
from interfaces.web.debug.messaging_policy_observability_nav.json_controller import MessagingPolicyObservabilityNavJsonController
from interfaces.web.debug.messaging_policy_observability_nav.page_presenter import default_tenant_id


class MessagingPolicyObservabilityNavRouteBundle:
    def __init__(self):
        self._json = MessagingPolicyObservabilityNavJsonController()
        self._html = MessagingPolicyObservabilityNavHtmlController()

    def json(self, *, tenant_id):
        return self._json.get_page(tenant_id=default_tenant_id(tenant_id))

    def html(self, *, tenant_id):
        return self._html.get_page(tenant_id=default_tenant_id(tenant_id))
