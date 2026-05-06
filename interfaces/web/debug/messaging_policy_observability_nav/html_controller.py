from __future__ import annotations

from interfaces.web.debug.common.html_escape import esc
from interfaces.web.debug.common.http_response import HttpResponse
from interfaces.web.debug.messaging_policy_observability_nav.page_presenter import present_page


def _build_card(item) -> str:
    return (
        "<div style='border:1px solid #d7dbe3;border-radius:14px;padding:16px;background:#fff;'>"
        f"<h3 style='margin:0 0 8px;'>{esc(item.title)}</h3>"
        f"<div style='color:#687285;font-size:14px;margin-bottom:10px;'>{esc(item.description)}</div>"
        f"<div style='font-size:13px;color:#687285;margin-bottom:12px;'><code>{esc(item.path)}</code></div>"
        f"<a href='{esc(item.href)}' style='display:inline-block;border:1px solid #d7dbe3;border-radius:10px;padding:10px 14px;text-decoration:none;color:#1d2433;'>Open</a>"
        "</div>"
    )


def build_page_html(model) -> str:
    cards = ''.join(_build_card(item) for item in model.items)
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Messaging Policy Observability</title></head>"
        "<body style='font-family:Arial,sans-serif;padding:24px;background:#f7f8fb;color:#1d2433;'>"
        "<div style='max-width:1100px;margin:0 auto;'>"
        "<h1 style='margin:0 0 8px;'>Messaging Policy Observability</h1>"
        f"<p style='color:#687285;margin:0 0 20px;'><strong>tenant_id:</strong> {esc(model.tenant_id)}</p>"
        "<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;'>"
        f"{cards}</div></div></body></html>"
    )


class MessagingPolicyObservabilityNavHtmlController:
    def get_page(self, *, tenant_id) -> HttpResponse:
        model = present_page(tenant_id=tenant_id)
        return HttpResponse(
            status_code=200,
            content_type='text/html; charset=utf-8',
            body=build_page_html(model),
        )
