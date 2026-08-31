from collections.abc import Mapping

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from runtime.business_autonomy.provider_payload_normalizers import ProviderPayloadNormalizers
from runtime.business_autonomy.provider_webhook_runtime import RAW_SIGNATURE_FIRST_PROVIDER_KEYS

CANON_FASTAPI_PROVIDER_WEBHOOK_ROUTES = True

def register_provider_webhook_routes(*, router, provider_admin_handlers) -> None:
    @router.post('/providers/webhook/{tenant_id}/{business_id}/{provider_key}', response_model=None)
    async def public_provider_webhook_ingest(tenant_id: str, business_id: str, provider_key: str, request: Request) -> dict | Response:
        headers = {str(k): str(v) for k, v in request.headers.items()}
        raw_body = await request.body()
        parsed = {} if provider_key in RAW_SIGNATURE_FIRST_PROVIDER_KEYS else ProviderPayloadNormalizers.parse_webhook_json(raw_body)
        nested_event = parsed.get('event') if isinstance(parsed.get('event'), Mapping) else {}
        event_key = str(headers.get('X-Event-Id') or headers.get('X-Shopify-Webhook-Id') or headers.get('X-Request-Id') or '').strip() or str(parsed.get('event_id') or parsed.get('id') or nested_event.get('client_msg_id') or nested_event.get('event_ts') or '').strip() or request.headers.get('x-amz-request-id', '') or request.headers.get('cf-ray', '') or 'payload-digest-fallback'
        topic = str(headers.get('X-Topic') or headers.get('X-Shopify-Topic') or headers.get('X-Webhook-Topic') or '').strip() or str(nested_event.get('type') or parsed.get('type') or '').strip()
        result = provider_admin_handlers.ingest_provider_webhook(payload={'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'headers': headers, 'body': raw_body.decode('utf-8', errors='ignore'), 'event_key': event_key, 'topic': topic, 'owner_id': 'public_provider_webhook'})
        if result.get('status') == 'invalid_signature' and provider_key in {'vk_messaging', 'max_messaging', 'slack_messaging', 'discord_messaging', 'line_messaging', 'viber_messaging'}:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED if provider_key == 'discord_messaging' else status.HTTP_403_FORBIDDEN, detail='provider_webhook_signature_denied')
        if provider_key == 'slack_messaging' and str(parsed.get('type') or '') == 'url_verification':
            challenge = str(parsed.get('challenge') or '')
            if not challenge:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='slack_url_verification_incomplete')
            return Response(content=challenge, media_type='text/plain')
        if provider_key == 'discord_messaging' and parsed.get('type') in {0, 1}:
            return Response(status_code=status.HTTP_204_NO_CONTENT) if parsed.get('type') == 0 or isinstance(parsed.get('event'), Mapping) else JSONResponse({'type': 1})
        if (result.get('metadata', {}).get('messaging_handoff') or result.get('metadata', {}).get('batch_results')) and not result.get('transport_ack_safe'):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='provider_webhook_processing_incomplete')
        if provider_key == 'vk_messaging':
            if not result.get('response_body'):
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='vk_callback_processing_incomplete')
            return Response(content=str(result['response_body']), media_type='text/plain')
        return result
