from __future__ import annotations

from pathlib import Path

from interfaces.web.settings.alert_subscriptions_integration.html_controller import HtmlController
from interfaces.web.settings.alert_subscriptions_integration.page_controller import PageController
from interfaces.web.settings.common.page_query import PageQuery
from interfaces.web.settings.common.save_command import SaveCommand
from interfaces.web.settings.alert_subscriptions_integration.save_controller import SaveController
from interfaces.web.settings.alert_subscriptions_integration.static_controller import StaticController
from interfaces.web.settings.common.http_payload_reader import read_payload
from interfaces.web.settings.common.tenant_reader import read_tenant_id


class AlertSubscriptionsRouteBundle:
    def __init__(self, *, project_root: Path, settings_gateway):
        self._html = HtmlController()
        self._page = PageController(settings_gateway=settings_gateway)
        self._save = SaveController(settings_gateway=settings_gateway)
        self._static = StaticController(root=project_root)

    def html(self):
        return self._html.get_page(
            css_href="/static/alert_subscriptions.css",
            js_src="/static/alert_subscriptions.js",
            model_endpoint="/api/settings/alert-subscriptions",
            save_endpoint="/api/settings/alert-subscriptions",
        )

    def model(self, *, tenant_id):
        return self._page.get_model(PageQuery(tenant_id=read_tenant_id(tenant_id)))

    def save(self, *, tenant_id, payload):
        return self._save.save(
            SaveCommand(
                tenant_id=read_tenant_id(tenant_id),
                payload=read_payload(payload),
            )
        )

    def css(self):
        return self._static.get_css()

    def js(self):
        return self._static.get_js()
