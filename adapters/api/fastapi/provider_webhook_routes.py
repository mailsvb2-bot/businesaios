from fastapi import HTTPException, Request, Response, status
CANON_FASTAPI_PROVIDER_WEBHOOK_ROUTES = True
def register_provider_webhook_routes(*, router, provider_admin_handlers) -> None:
    @router.post('/providers/webhook/{tenant_id}/{business_id}/{provider_key}', response_model=None)
    async def public_provider_webhook_ingest(tenant_id: str, business_id: str, provider_key: str, request: Request) -> dict | Response:
        headers = {str(k): str(v) for k, v in request.headers.items()}
        event_key = str(headers.get('X-Event-Id') or headers.get('X-Shopify-Webhook-Id') or headers.get('X-Request-Id') or '').strip() or request.headers.get('x-amz-request-id', '') or request.headers.get('cf-ray', '') or 'payload-digest-fallback'
        result = provider_admin_handlers.ingest_provider_webhook(payload={'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'headers': headers, 'body': (await request.body()).decode('utf-8', errors='ignore'), 'event_key': event_key, 'topic': str(headers.get('X-Topic') or headers.get('X-Shopify-Topic') or headers.get('X-Webhook-Topic') or '').strip(), 'owner_id': 'public_provider_webhook'})
        if provider_key in {'vk_messaging', 'max_messaging'} and result.get('status') == 'invalid_signature':
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='provider_webhook_signature_denied')
        if result.get('metadata', {}).get('messaging_handoff') and not result.get('transport_ack_safe'):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='provider_webhook_processing_incomplete')
        if provider_key == 'vk_messaging':
            if not result.get('response_body'):
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='vk_callback_processing_incomplete')
            return Response(content=str(result['response_body']), media_type='text/plain')
        return result
