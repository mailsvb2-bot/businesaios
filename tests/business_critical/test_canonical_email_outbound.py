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

    def __init__(self, host: str, port: int, *, timeout: float) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.calls: list[str] = []
        self.message = None
        self.__class__.instances.append(self)

    def ehlo(self) -> None:
        self.calls.append("ehlo")

    def starttls(self) -> None:
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
