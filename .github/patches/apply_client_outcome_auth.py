from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match, got {count}: {old!r}")
    return text.replace(old, new, 1)


path = Path("adapters/api/fastapi/public_routes.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "            if security_guard.requires_external_auth(route_path) and auth_bundle is not None:\n",
    "            if security_guard.requires_external_auth(route_path):\n"
    "                if auth_bundle is None:\n"
    "                    raise PermissionError('api_perimeter_auth_unconfigured')\n",
)

routes = (
    "/client-outcome/select",
    "/client-outcome/orders/{order_id}/amend",
    "/client-outcome/execute",
    "/client-outcome/disputes/open",
    "/client-outcome/disputes/reverse",
    "/client-outcome/full-cycle",
    "/client-outcome/admin-summary",
)
for route in routes:
    old = f"            enforce_public_security(route_path='{route}', request_context=ctx, body=request.model_dump())\n"
    new = (
        "            enforce_public_security(\n"
        f"                route_path='{route}',\n"
        "                request_context=ctx,\n"
        "                body=request.model_dump(),\n"
        "                http_request=http_request,\n"
        "            )\n"
    )
    text = replace_once(text, old, new)

admin_route = "/client-outcome/orders/{order_id}/{lead_id}/admin-view"
text = replace_once(
    text,
    f"            enforce_public_security(route_path='{admin_route}', request_context=ctx, body={{'order_id': order_id, 'lead_id': lead_id}})\n",
    "            enforce_public_security(\n"
    f"                route_path='{admin_route}',\n"
    "                request_context=ctx,\n"
    "                body={'order_id': order_id, 'lead_id': lead_id},\n"
    "                http_request=http_request,\n"
    "            )\n",
)

path.write_text(text, encoding="utf-8")
