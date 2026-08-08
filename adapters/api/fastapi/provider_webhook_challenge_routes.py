from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime

CANON_PROVIDER_WEBHOOK_CHALLENGE_ROUTES = True


def register_provider_webhook_challenge_routes(*, router: APIRouter, dependency_container) -> None:
    @router.get('/providers/webhook/{tenant_id}/{business_id}/whatsapp_cloud', tags=['provider-runtime'])
    async def whatsapp_webhook_challenge(tenant_id: str, business_id: str, request: Request) -> Response:
        query = request.query_params
        challenge = ProviderWebhookRuntime(dependency_container.secret_vault).verify_challenge(provider=provider_map()['whatsapp_cloud'], tenant_id=tenant_id, business_id=business_id, mode=query.get('hub.mode', ''), verify_token=query.get('hub.verify_token', ''), challenge=query.get('hub.challenge', ''))
        if challenge is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='whatsapp_webhook_challenge_denied')
        return Response(content=challenge, media_type='text/plain')


__all__ = ['CANON_PROVIDER_WEBHOOK_CHALLENGE_ROUTES', 'register_provider_webhook_challenge_routes']
