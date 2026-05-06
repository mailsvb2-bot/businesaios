from __future__ import annotations

from interfaces.api.action_models import ExecuteActionRequest
from interfaces.api.execute_action_handler import ExecuteActionHandler
from entrypoints.api.request_context import RequestContext


class _MinimalService:
    def __init__(self) -> None:
        self.last_action = None

    def execute_action(self, action):
        self.last_action = action
        return {
            'status': 'ok',
            'action_type': action.action_type,
            'reason': 'executed',
            'details': {'echo': dict(action.payload)},
        }


class _IdentityAwareService:
    def __init__(self) -> None:
        self.last_action = None
        self.last_request_context = None
        self.last_idempotency_key = None
        self.last_action_id = None

    def execute_action(self, action, *, request_context=None, idempotency_key=None, action_id=None):
        self.last_action = action
        self.last_request_context = request_context
        self.last_idempotency_key = idempotency_key
        self.last_action_id = action_id
        return {
            'status': 'ok',
            'action_type': action.action_type,
            'reason': 'executed',
            'details': {'echo': dict(action.payload)},
        }


def test_execute_action_handler_canonicalizes_identity_into_action_payload() -> None:
    service = _MinimalService()
    handler = ExecuteActionHandler(application_service=service)
    context = RequestContext(tenant_id='tenant-a', request_id='req-1')

    response = handler.handle(
        ExecuteActionRequest(action_type='launch', payload={'channel': 'email'}),
        request_context=context,
        idempotency_key='idem-1',
        action_id='action-1',
    )

    assert response.status == 'ok'
    assert service.last_action is not None
    assert service.last_action.payload['channel'] == 'email'
    assert service.last_action.payload['tenant_id'] == 'tenant-a'
    assert service.last_action.payload['idempotency_key'] == 'idem-1'
    assert service.last_action.payload['action_id'] == 'action-1'


def test_execute_action_handler_threads_identity_to_application_service_when_supported() -> None:
    service = _IdentityAwareService()
    handler = ExecuteActionHandler(application_service=service)
    context = RequestContext(tenant_id='tenant-a', request_id='req-2')

    response = handler.handle(
        ExecuteActionRequest(action_type='launch', payload={}),
        request_context=context,
        idempotency_key='idem-2',
        action_id='action-2',
    )

    assert response.status == 'ok'
    assert service.last_request_context is context
    assert service.last_idempotency_key == 'idem-2'
    assert service.last_action_id == 'action-2'
    assert service.last_action.payload['tenant_id'] == 'tenant-a'


def test_execute_action_handler_uses_request_context_request_id_as_canonical_fallback_identity() -> None:
    service = _MinimalService()
    handler = ExecuteActionHandler(application_service=service)
    context = RequestContext(tenant_id='tenant-a', request_id='req-fallback')

    response = handler.handle(
        ExecuteActionRequest(action_type='launch', payload={}),
        request_context=context,
    )

    assert response.status == 'ok'
    assert service.last_action.payload['tenant_id'] == 'tenant-a'
    assert service.last_action.payload['idempotency_key'] == 'req-fallback'
    assert service.last_action.payload['action_id'] == 'req-fallback'


class _KwargsOnlyService:
    def __init__(self) -> None:
        self.last_kwargs = None

    def execute_action(self, **kwargs):
        self.last_kwargs = dict(kwargs)
        action = kwargs['action']
        return {
            'status': 'ok',
            'action_type': action.action_type,
            'reason': 'executed',
            'details': {'echo': dict(action.payload)},
        }


def test_execute_action_handler_threads_identity_into_kwargs_only_application_service() -> None:
    service = _KwargsOnlyService()
    handler = ExecuteActionHandler(application_service=service)
    context = RequestContext(tenant_id='tenant-a', request_id='req-kwargs')

    response = handler.handle(
        ExecuteActionRequest(action_type='launch', payload={}),
        request_context=context,
        idempotency_key='idem-kwargs',
        action_id='action-kwargs',
    )

    assert response.status == 'ok'
    assert service.last_kwargs is not None
    assert service.last_kwargs['request_context'] is context
    assert service.last_kwargs['idempotency_key'] == 'idem-kwargs'
    assert service.last_kwargs['action_id'] == 'action-kwargs'
    assert service.last_kwargs['tenant_id'] == 'tenant-a'
