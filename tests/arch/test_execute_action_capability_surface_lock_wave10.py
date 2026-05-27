from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_route_handlers_delegate_execute_action_to_canonical_handler() -> None:
    text = (ROOT / 'entrypoints' / 'api' / 'route_handlers.py').read_text(encoding='utf-8')
    assert 'ExecuteActionHandler' in text
    assert 'return handler.handle(' in text
    assert 'map_execute_action_request' not in text
    assert 'present_execute_action_response(result)' not in text


def test_response_presenter_owns_capability_surface_normalization() -> None:
    text = (ROOT / 'entrypoints' / 'api' / 'response_presenter.py').read_text(encoding='utf-8')
    assert 'normalize_capability_view(' in text
    assert 'present_blocked_execute_action_response' in text


def test_execute_action_wrappers_do_not_parse_capability_surface() -> None:
    control_plane = (ROOT / 'entrypoints' / 'api' / 'execute_action_with_control_plane.py').read_text(encoding='utf-8')
    guards = (ROOT / 'entrypoints' / 'api' / 'execute_action_with_guards.py').read_text(encoding='utf-8')
    assert 'present_blocked_execute_action_response(' in control_plane
    assert 'capability_view' not in control_plane
    assert 'capability_diagnostics' not in control_plane
    assert 'capability_view' not in guards
    assert 'capability_diagnostics' not in guards


def test_fastapi_router_builds_one_canonical_execute_action_stack_when_dependencies_exist() -> None:
    text = (ROOT / 'adapters' / 'api' / 'fastapi' / 'router_adapter.py').read_text(encoding='utf-8')
    assert 'build_runtime_api_bundle(' in text
    assert 'handler_bundle = runtime_api_bundle.handler_bundle' in text
    assert 'request_context = (dependency_container.request_context' not in text


def test_execute_action_stack_centralizes_wrapper_composition() -> None:
    text = (ROOT / 'interfaces' / 'api' / 'execute_action_api_stack.py').read_text(encoding='utf-8')
    bundle = (ROOT / 'entrypoints' / 'api' / 'execute_action_stack_bundle.py').read_text(encoding='utf-8')
    assert 'ExecuteActionHandler -> reliability guards -> control-plane envelope' in text
    assert 'build_execute_action_guarded_handler(' in bundle
    assert 'build_execute_action_control_plane(' in bundle


def test_execute_action_stack_uses_canonical_durable_idempotency_bridge_when_available() -> None:
    text = (ROOT / 'interfaces' / 'api' / 'execute_action_api_stack.py').read_text(encoding='utf-8')
    bridge = (ROOT / 'entrypoints' / 'api' / 'execute_action_idempotency_store.py').read_text(encoding='utf-8')
    assert 'build_api_execute_action_idempotency_store' in text
    assert 'DurableExecuteActionIdempotencyStore' in bridge
    assert 'response_payload' in bridge


def test_fastapi_execute_action_route_threads_header_identity() -> None:
    text = (ROOT / 'adapters' / 'api' / 'fastapi' / 'router_adapter.py').read_text(encoding='utf-8')
    public_routes = (ROOT / 'adapters' / 'api' / 'fastapi' / 'public_routes.py').read_text(encoding='utf-8')
    assert 'x-idempotency-key' in public_routes
    assert 'x-action-id' in public_routes
    assert 'idempotency_key=idempotency_key' in public_routes
    assert 'action_id=action_id' in public_routes


def test_execute_action_wrappers_use_canonical_audit_payload_builder_and_tenant_scoped_idempotency_keys() -> None:
    guards = (ROOT / 'entrypoints' / 'api' / 'execute_action_with_guards.py').read_text(encoding='utf-8')
    control_plane = (ROOT / 'entrypoints' / 'api' / 'execute_action_with_control_plane.py').read_text(encoding='utf-8')
    audit_payload = (ROOT / 'entrypoints' / 'api' / 'execute_action_audit_payload.py').read_text(encoding='utf-8')
    assert 'build_execute_action_audit_payload' in guards
    assert 'build_execute_action_audit_payload' in control_plane
    assert "return f'{prefix}::{str(idempotency_key).strip()}'" in guards
    assert 'request_context.redacted_dict()' in audit_payload


def test_control_plane_replay_bypasses_quota_and_wrapper_fallback_keeps_identity_path() -> None:
    route_handlers = (ROOT / 'entrypoints' / 'api' / 'route_handlers.py').read_text(encoding='utf-8')
    control_plane = (ROOT / 'entrypoints' / 'api' / 'execute_action_with_control_plane.py').read_text(encoding='utf-8')
    handler = (ROOT / 'entrypoints' / 'api' / 'execute_action_handler.py').read_text(encoding='utf-8')
    request_context = (ROOT / 'entrypoints' / 'api' / 'request_context.py').read_text(encoding='utf-8')
    assert 'request_context=request_context' in route_handlers
    assert 'idempotency_key=idempotency_key' in route_handlers
    assert 'action_id=action_id' in route_handlers
    assert 'has_completed_response' in control_plane
    assert 'control_plane.quota_bypassed_replay' in control_plane
    assert 'control_plane.replayed' in control_plane
    assert 'request_context: RequestContext | None = None' in handler
    assert "object.__setattr__(derived, '_generated_request_id', self._generated_request_id)" in request_context


def test_execute_action_idempotency_truth_path_handles_in_progress_duplicates_canonically() -> None:
    guards = (ROOT / 'entrypoints' / 'api' / 'execute_action_with_guards.py').read_text(encoding='utf-8')
    control_plane = (ROOT / 'entrypoints' / 'api' / 'execute_action_with_control_plane.py').read_text(encoding='utf-8')
    executor = (ROOT / 'infra' / 'idempotency.py').read_text(encoding='utf-8')
    bridge = (ROOT / 'entrypoints' / 'api' / 'execute_action_idempotency_store.py').read_text(encoding='utf-8')
    assert 'IdempotencyInProgressError' in executor
    assert 'def status(self, *, key: str)' in executor
    assert 'guards.idempotency_in_progress' in guards
    assert 'guards.idempotency_terminal_failed' in guards
    assert 'control_plane.quota_bypassed_in_progress' in control_plane
    assert 'control_plane.idempotency_in_progress' in control_plane
    assert 'def reserve(self, key: str)' in bridge
    assert 'def mark_completed(self, key: str, value: object)' in bridge


def test_execute_action_stack_default_uses_canonical_reliability_idempotency_store() -> None:
    stack = (ROOT / 'interfaces' / 'api' / 'execute_action_api_stack.py').read_text(encoding='utf-8')
    bridge = (ROOT / 'entrypoints' / 'api' / 'execute_action_idempotency_store.py').read_text(encoding='utf-8')
    assert 'ReliabilityInMemoryIdempotencyStore' in stack
    assert 'return build_api_execute_action_idempotency_store(ReliabilityInMemoryIdempotencyStore())' in stack
    assert 'ReliabilityInMemoryIdempotencyStore' in bridge


def test_execute_action_handler_owns_request_envelope_normalization_and_application_service_identity_threading() -> None:
    handler = (ROOT / 'entrypoints' / 'api' / 'execute_action_handler.py').read_text(encoding='utf-8')
    envelope = (ROOT / 'entrypoints' / 'api' / 'execute_action_request_envelope.py').read_text(encoding='utf-8')
    signature_binding = (ROOT / 'entrypoints' / 'api' / 'signature_binding.py').read_text(encoding='utf-8')
    assert 'canonicalize_execute_action_request(' in handler
    assert 'supported_kwargs(' in handler
    assert 'tenant_id=tenant_id' in handler
    assert 'def supported_kwargs(' in signature_binding
    assert "payload['tenant_id'] = tenant_id" in envelope
    assert "payload['idempotency_key'] = explicit_idempotency_key" in envelope
    assert "payload['action_id'] = explicit_action_id" in envelope


def test_fastapi_router_uses_shared_audit_logs_for_execute_action_and_control_plane() -> None:
    router = (ROOT / 'adapters' / 'api' / 'fastapi' / 'router_adapter.py').read_text(encoding='utf-8')
    dependencies = (ROOT / 'adapters' / 'api' / 'fastapi' / 'dependencies.py').read_text(encoding='utf-8')
    assert 'shared_action_audit_log = dependency_container.action_audit_log()' in router
    assert 'action_audit_log=shared_action_audit_log' in router
    assert 'AuditRouteHandlers(action_audit_log=shared_action_audit_log' in router
    assert 'WebhookRouteHandlers(verifier=build_webhook_verifier(), audit_log=shared_action_audit_log, security_guard=security_bundle.webhook_surface_guard)' in router
    assert 'def action_audit_log(self) -> ActionAuditLog:' in dependencies
    assert 'def decision_audit_log(self) -> DecisionAuditLog:' in dependencies


def test_execute_action_audit_payload_redacts_request_payload() -> None:
    payload_builder = (ROOT / 'entrypoints' / 'api' / 'execute_action_audit_payload.py').read_text(encoding='utf-8')
    assert 'PayloadRedactor' in payload_builder
    assert "'request_payload': redactor.redact(dict(request.payload))" in payload_builder


def test_decision_audit_log_has_file_backed_default_and_router_uses_shared_instance() -> None:
    router = (ROOT / 'adapters' / 'api' / 'fastapi' / 'router_adapter.py').read_text(encoding='utf-8')
    dependencies = (ROOT / 'adapters' / 'api' / 'fastapi' / 'dependencies.py').read_text(encoding='utf-8')
    audit_handlers = (ROOT / 'entrypoints' / 'api' / 'audit_route_handlers.py').read_text(encoding='utf-8')
    decision_audit = (ROOT / 'observability' / 'decision_audit_log.py').read_text(encoding='utf-8')
    assert 'build_default_decision_audit_log' in decision_audit
    assert 'FileDecisionAuditLog' in decision_audit
    assert 'shared_decision_audit_log = dependency_container.decision_audit_log() if dependency_container is not None else build_default_decision_audit_log()' in router
    assert 'AuditRouteHandlers(action_audit_log=shared_action_audit_log, decision_audit_log=shared_decision_audit_log)' in router
    assert 'return build_default_decision_audit_log(config_surface=self.config_surface)' in dependencies
    assert 'field(default_factory=build_default_decision_audit_log)' in audit_handlers


def test_http_boot_delegates_to_canonical_http_boot_surface() -> None:
    text = Path('boot/http_boot.py').read_text(encoding='utf-8')
    assert 'build_http_boot_surface' in text
    assert 'create_fastapi_app(' not in text


def test_audit_logs_use_canonical_storage_policy() -> None:
    action_text = Path('observability/action_audit_log.py').read_text(encoding='utf-8')
    decision_text = Path('observability/decision_audit_log.py').read_text(encoding='utf-8')
    assert 'build_default_audit_storage_policy' in action_text
    assert 'rotate_audit_file' in action_text
    assert 'build_default_audit_storage_policy' in decision_text
    assert 'rotate_audit_file' in decision_text
