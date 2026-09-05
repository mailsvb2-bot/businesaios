from __future__ import annotations

from pathlib import Path

import pytest

from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_truth_matrix import provider_truth_map
from contracts.email_outbound import EmailOutboundPayloadV1, normalize_email_address
from runtime.business_autonomy.provider_connector_health import ProviderConnectorHealthService
from runtime.business_autonomy.provider_live_probe_runtime import ProviderLiveProbeRuntime
from runtime.business_autonomy.provider_vendor_transports import build_provider_vendor_transports
from runtime.messaging.bootstrap import _NativeProviderQueueAdapter, build_multichannel_dispatcher
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def _put(vault: InMemorySecretVault, provider, business_id: str, name: str, value: str) -> None:
    ref = SecretRef(
        tenant_id="tenant-a",
        connector_id=provider.connector_id,
        scope=business_id,
        secret_name=f"{provider.connector_id}.{name}",
    )
    vault.put(SecretRecord(ref=ref, ciphertext=b"pending", source=SecretSource.CONNECTOR), plaintext=value.encode())


def _configured_vault() -> tuple[object, InMemorySecretVault]:
    provider = provider_map()["email_connector"]
    vault = InMemorySecretVault()
    for name, value in {
        "smtp_host": "smtp.example.test",
        "smtp_port": "587",
        "smtp_security": "starttls",
        "smtp_username": "sender@example.test",
        "smtp_password": "secret-password",
        "from_address": "sender@example.test",
    }.items():
        _put(vault, provider, "biz-a", name, value)
    return provider, vault


class _SMTP:
    instances: list[_SMTP] = []

    def __init__(self, host: str, port: int, *, timeout: float, context=None) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.context = context
        self.starttls_context = None
        self.calls: list[str] = []
        self.message = None
        self.__class__.instances.append(self)

    def ehlo(self) -> None:
        self.calls.append("ehlo")

    def starttls(self, *, context=None) -> None:
        self.starttls_context = context
        self.calls.append("starttls")

    def login(self, _username: str, _password: str) -> None:
        self.calls.append("login")

    def noop(self):
        self.calls.append("noop")
        return 250, b"ok"

    def send_message(self, message):
        self.calls.append("send_message")
        self.message = message
        return {}

    def quit(self) -> None:
        self.calls.append("quit")


class _AmbiguousSMTP(_SMTP):
    def send_message(self, message):
        import smtplib

        self.calls.append("send_message")
        self.message = message
        raise smtplib.SMTPServerDisconnected("connection lost after DATA")


def test_email_contract_rejects_header_injection_and_bounds_payload() -> None:
    assert normalize_email_address("Test@Example.ORG") == "test@example.org"
    with pytest.raises(ValueError):
        normalize_email_address("victim@example.org\nBcc: other@example.org")
    payload = EmailOutboundPayloadV1("user@example.org", "  Subject  line ", " body ")
    assert payload.recipient == "user@example.org" and payload.subject == "Subject line" and payload.body == "body"
    with pytest.raises(ValueError):
        EmailOutboundPayloadV1("user@example.org", "", "body")


def test_email_provider_is_guarded_queue_backed_and_not_falsely_full_live_ready() -> None:
    provider = provider_map()["email_connector"]
    truth = provider_truth_map()["email_connector"]
    fields = {field.secret_name for field in provider.secret_fields}
    assert {"smtp_host", "smtp_port", "smtp_security", "from_address", "smtp_password"} <= fields
    assert truth.write_supported is True and truth.approval_required is True
    assert truth.live_ready is False
    dispatcher = build_multichannel_dispatcher()
    adapter = dispatcher.adapters["email"]
    assert isinstance(adapter, _NativeProviderQueueAdapter)
    assert adapter.provider_key == "email_connector"


def test_email_health_validates_vault_smtp_configuration() -> None:
    provider, vault = _configured_vault()
    health = ProviderConnectorHealthService(vault)
    live = health.probe(provider=provider, tenant_id="tenant-a", business_id="biz-a", probe_mode="live")
    assert live.status == "ready_for_live_probe"
    broken = InMemorySecretVault()
    for name, value in {"smtp_host": "bad host", "smtp_port": "587", "smtp_security": "starttls", "from_address": "sender@example.test"}.items():
        _put(broken, provider, "biz-a", name, value)
    result = ProviderConnectorHealthService(broken).probe(provider=provider, tenant_id="tenant-a", business_id="biz-a", probe_mode="live")
    assert result.status == "invalid_secret_shape" and result.reason == "invalid_smtp_configuration"


def test_email_live_probe_and_send_use_sealed_smtp_owner(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    import runtime._internal.effects_clients.provider_outbound_sender as sender

    _SMTP.instances.clear()
    monkeypatch.setattr(sender.smtplib, "SMTP", _SMTP)
    monkeypatch.setattr(sender.smtplib, "SMTP_SSL", _SMTP)
    provider, vault = _configured_vault()
    probe = ProviderLiveProbeRuntime(vault).run(provider=provider, tenant_id="tenant-a", business_id="biz-a", mode="live")
    assert probe.status == "probe_live_ok" and probe.ok is True
    transport = build_provider_vendor_transports(vault, bind_live_network=True)["email_connector"]
    base = {
        "recipient": "recipient@example.org",
        "subject": "Proposal",
        "body": "Hello",
        "_allow_network": True,
        "_provider_write_approved": True,
        "_provider_queue_job_id": "provider-sync-email_connector-fixed-job",
    }
    first = transport.execute(provider=provider, tenant_id="tenant-a", business_id="biz-a", operation="message_send", payload=base)
    second = transport.execute(provider=provider, tenant_id="tenant-a", business_id="biz-a", operation="message_send", payload=base)
    first_id = first["parsed_response"]["resource_id"]
    second_id = second["parsed_response"]["resource_id"]
    assert first["_response_ok"] is True and first_id == second_id
    assert first_id.startswith("<baios-") and first["parsed_response"]["delivery_state"] == "accepted"
    assert _SMTP.instances[-1].message["Auto-Submitted"] == "auto-generated"


def test_email_smtp_tls_verifies_certificate_and_hostname(monkeypatch) -> None:
    import ssl

    import runtime._internal.effects_clients.provider_outbound_sender as sender

    _SMTP.instances.clear()
    monkeypatch.setattr(sender.smtplib, "SMTP", _SMTP)
    monkeypatch.setattr(sender.smtplib, "SMTP_SSL", _SMTP)
    starttls_client = sender._smtp_connect_explicit(
        host="smtp.example.test", port=587, security="starttls", username="", password="", timeout_s=5.0,
    )
    starttls_context = starttls_client.starttls_context
    assert starttls_context is not None
    assert starttls_context.verify_mode == ssl.CERT_REQUIRED and starttls_context.check_hostname is True
    starttls_client.quit()

    ssl_client = sender._smtp_connect_explicit(
        host="smtp.example.test", port=465, security="ssl", username="", password="", timeout_s=5.0,
    )
    assert ssl_client.context is not None
    assert ssl_client.context.verify_mode == ssl.CERT_REQUIRED and ssl_client.context.check_hostname is True
    ssl_client.quit()


def test_email_send_after_smtp_boundary_is_ambiguous_and_not_retryable(monkeypatch) -> None:
    import runtime._internal.effects_clients.provider_outbound_sender as sender

    monkeypatch.setattr(sender.smtplib, "SMTP", _AmbiguousSMTP)
    monkeypatch.setattr(sender.smtplib, "SMTP_SSL", _AmbiguousSMTP)
    provider, vault = _configured_vault()
    transport = build_provider_vendor_transports(vault, bind_live_network=True)["email_connector"]
    result = transport.execute(
        provider=provider,
        tenant_id="tenant-a",
        business_id="biz-a",
        operation="message_send",
        payload={
            "recipient": "recipient@example.org",
            "subject": "Proposal",
            "body": "Hello",
            "_allow_network": True,
            "_provider_write_approved": True,
            "_provider_queue_job_id": "provider-sync-email_connector-ambiguous",
        },
    )
    parsed = result["parsed_response"]
    assert result["_response_ok"] is False
    assert parsed["delivery_state"] == "unknown"
    assert parsed["error_category"] == "ambiguous_delivery"
    assert parsed["error_code"] is None and parsed["retryable"] is False


def test_smtplib_has_one_production_owner() -> None:
    root = Path(__file__).resolve().parents[2]
    owners = []
    for area in ("runtime", "application", "interfaces", "core", "execution", "contracts"):
        for path in (root / area).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "import smtplib" in text or "from smtplib import" in text:
                owners.append(path.relative_to(root).as_posix())
    assert owners == ["runtime/_internal/effects_clients/provider_outbound_sender.py"]


def test_send_message_action_preserves_email_subject_to_outbound_message() -> None:
    from types import SimpleNamespace

    from core.actions.catalog import build_catalog
    from runtime.handlers_messaging import handle_send_message

    catalog = build_catalog()
    schema = catalog["send_message@v1"].schema
    schema.validate({"tenant_id": "tenant-a", "user_id": "user@example.org", "text": "Body", "subject": "Proposal", "channel": "email"})

    captured = {}

    class _Effects:
        def send_message(self, **kwargs):
            captured.update(kwargs)
            return {"ok": True}

    env = SimpleNamespace(decision=SimpleNamespace(decision_id="dec-1", correlation_id="corr-1"))
    handle_send_message({"tenant_id": "tenant-a", "user_id": "user@example.org", "text": "Body", "subject": "Proposal", "channel": "email"}, _Effects(), env)
    assert captured["subject"] == "Proposal" and captured["text"] == "Body" and captured["channel"] == "email"


def test_email_subject_survives_sealed_outbound_message_factory() -> None:
    from runtime._internal.effects_actions.telegram.messaging_parts.message_factory import build_outbound_message

    msg = build_outbound_message(
        decision_id="dec-1", correlation_id="corr-1", user_id="user@example.org", text="Body",
        tenant_id="tenant-a", subject="Proposal", business_id="biz-a", reply_markup=None,
        callback_query_id=None, track_event_type=None, track_payload=None, channel="email",
        priority="normal", critical=True,
    )
    assert msg.payload["subject"] == "Proposal"


def test_marketing_offer_without_llm_uses_fallback_text_and_preserves_email_subject() -> None:
    from types import SimpleNamespace

    from core.actions.catalog import build_catalog
    from runtime.handlers_messaging import handle_send_marketing_offer

    schema = build_catalog()["send_marketing_offer@v1"].schema
    schema.validate({
        "tenant_id": "tenant-a", "user_id": "user@example.org", "channel": "email",
        "subject": "Proposal", "offer": {"id": "offer-1"}, "fallback_text": "Useful offer",
    })
    captured = {}

    class _Effects:
        def send_message(self, **kwargs):
            captured.update(kwargs)
            return {"ok": True}

    env = SimpleNamespace(decision=SimpleNamespace(decision_id="dec-1", correlation_id="corr-1"))
    handle_send_marketing_offer(
        {"tenant_id": "tenant-a", "business_id": "biz-a", "user_id": "user@example.org", "channel": "email",
         "subject": "Proposal", "offer": {"id": "offer-1"}, "fallback_text": "Useful offer"},
        _Effects(), env, composer=None,
    )
    assert captured["text"] == "Useful offer"
    assert captured["subject"] == "Proposal"
    assert captured["business_id"] == "biz-a"
    assert captured["channel"] == "email"


def test_email_subject_and_business_scope_reach_existing_provider_queue() -> None:
    from runtime._internal.effects_actions.telegram.messaging_parts.message_factory import build_outbound_message

    provider = provider_map()["email_connector"]
    captured = {}

    class _Registry:
        def get(self, key):
            assert key == "email_connector"
            return provider

    class _Service:
        provider_registry = _Registry()

        def execute_queued_provider_sync(self, **kwargs):
            captured.update(kwargs)
            return {
                "dispatch": {"queued": True, "job_id": "job-1"},
                "result": {"accepted": True, "status": "live_executed", "parsed_response": {"resource_id": "<msg-1>"}},
            }

    msg = build_outbound_message(
        decision_id="dec-1", correlation_id="corr-1", user_id="user@example.org", text="Body",
        tenant_id="tenant-a", subject="Proposal", business_id="biz-a", reply_markup=None,
        callback_query_id=None, track_event_type=None, track_payload=None, channel="email",
        priority="normal", critical=True,
    )
    result = _NativeProviderQueueAdapter("email", service_factory=lambda: _Service()).send(msg)
    assert result.ok is True and result.mode == "accepted"
    assert captured["tenant_id"] == "tenant-a" and captured["business_id"] == "biz-a"
    assert captured["provider_key"] == "email_connector" and captured["operation"] == "message_send"
    assert captured["payload"]["recipient"] == "user@example.org"
    assert captured["payload"]["subject"] == "Proposal" and captured["payload"]["body"] == "Body"


def test_email_retrying_provider_job_stays_in_progress_for_messaging_policy() -> None:
    from runtime._internal.effects_actions.telegram.messaging_parts.message_factory import build_outbound_message

    provider = provider_map()["email_connector"]

    class _Registry:
        def get(self, key):
            assert key == "email_connector"
            return provider

    class _Service:
        provider_registry = _Registry()

        def execute_queued_provider_sync(self, **kwargs):
            return {
                "dispatch": {"queued": True, "job_id": "job-retry", "metadata": {"job_state": "pending"}},
                "worker": {"retried": 1, "job_state": "pending"},
                "result": {
                    "accepted": False,
                    "status": "live_execution_failed",
                    "parsed_response": {
                        "delivery_state": "not_attempted",
                        "error_code": "smtp_pre_send_transport_failure",
                        "retryable": True,
                    },
                    "error": {"category": "transport"},
                },
            }

    msg = build_outbound_message(
        decision_id="dec-retry", correlation_id="corr-retry", user_id="user@example.org", text="Body",
        tenant_id="tenant-a", subject="Proposal", business_id="biz-a", reply_markup=None,
        callback_query_id=None, track_event_type=None, track_payload=None, channel="email",
        priority="normal", critical=True,
    )
    result = _NativeProviderQueueAdapter("email", service_factory=lambda: _Service()).send(msg)
    assert result.ok is False
    assert result.mode == "in_progress"
    assert result.detail["job_state"] == "pending"
    assert result.detail["job_id"] == "job-retry"


def test_email_pending_retry_stops_cross_channel_fallback() -> None:
    from runtime._internal.effects_actions.telegram.messaging_parts.message_factory import build_outbound_message
    from runtime.messaging_policy.policy_plan import PolicyPlan
    from runtime.messaging_policy_events.execute_with_events import execute_policy_plan_with_events

    provider = provider_map()["email_connector"]
    calls: list[str] = []

    class _Registry:
        def get(self, key):
            assert key == "email_connector"
            return provider

    class _Service:
        provider_registry = _Registry()

        def execute_queued_provider_sync(self, **kwargs):
            return {
                "dispatch": {"queued": True, "job_id": "job-retry", "metadata": {"job_state": "pending"}},
                "worker": {"retried": 1, "job_state": "pending"},
                "result": {
                    "accepted": False,
                    "status": "live_execution_failed",
                    "parsed_response": {
                        "delivery_state": "not_attempted",
                        "error_code": "smtp_pre_send_transport_failure",
                        "retryable": True,
                    },
                    "error": {"category": "transport"},
                },
            }

    adapter = _NativeProviderQueueAdapter("email", service_factory=lambda: _Service())
    base = build_outbound_message(
        decision_id="dec-retry", correlation_id="corr-retry", user_id="user@example.org", text="Body",
        tenant_id="tenant-a", subject="Proposal", business_id="biz-a", reply_markup=None,
        callback_query_id=None, track_event_type=None, track_payload=None, channel="email",
        priority="normal", critical=True,
    )

    def send_once(msg):
        calls.append(msg.channel)
        if msg.channel == "email":
            result = adapter.send(msg)
            return result.ok, {**dict(result.detail or {}), "mode": result.mode}
        raise AssertionError("fallback channel must not run while email retry is pending")

    ok, meta = execute_policy_plan_with_events(
        plan=PolicyPlan(ordered_channels=("email", "vk"), reason_codes=("fallback",), terminal_reason=""),
        base_message=base,
        send_once=send_once,
    )
    assert ok is False
    assert calls == ["email"]
    assert meta["mode"] == "in_progress"
    assert meta["job_id"] == "job-retry"
    assert meta["policy"]["terminal_reason"] == "in_progress"
