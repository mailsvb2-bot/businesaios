from __future__ import annotations

from interfaces.web.settings.messaging_preferences.html_page import build_page
from interfaces.web.common.http_response import HttpResponse


class HtmlController:
    def get_page(
        self,
        *,
        css_href: str,
        js_src: str,
        model_endpoint: str,
        save_endpoint: str,
    ) -> HttpResponse:
        body = build_page(
            css_href=css_href,
            js_src=js_src,
            model_endpoint=model_endpoint,
            save_endpoint=save_endpoint,
        )
        return HttpResponse(
            status_code=200,
            content_type="text/html; charset=utf-8",
            body=body,
        )
