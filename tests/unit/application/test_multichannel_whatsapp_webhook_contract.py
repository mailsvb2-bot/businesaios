from __future__ import annotations

import hashlib
import hmac

from application.business_autonomy.provider_catalog import (
    BRIDGE_MESSAGING_PROVIDER_KEYS,
    MESSAGING_CHANNEL_PROVIDER_KEYS,
    provider_map,
)
from application.business_autonomy.provider_messaging_binding import describe_provider_messaging_binding
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def _put(vault, provider, name: str, value: str) -> None:
    ref = SecretRef(tenant_id="tenant-a", connector_id=provider.connector_id, scope="business-a", secret_name=f"{provider.connector_id}.{name}")
    vault.put(SecretRecord(ref=ref, ciphertext=b"pending", source=SecretSource.CONNECTOR), plaintext=value.encode())


def test_whatsapp_webhook_uses_app_secret_hmac_and_case_insensitive_header() -> None:
    provider = provider_map()["whatsapp_cloud"]
    vault = InMemorySecretVault()
    _put(vault, provider, "app_secret", "app-secret")
    body = b'{"object":"whatsapp_business_account"}'
    signature = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    runtime = ProviderWebhookRuntime(vault)
    assert runtime.describe(provider).verification_kind == "hmac_sha256_hex"
    assert runtime.verify(provider=provider, tenant_id="tenant-a", business_id="business-a", headers={"x-hub-signature-256": signature}, body=body) is True
    assert runtime.verify(provider=provider, tenant_id="tenant-a", business_id="business-a", headers={"X-Hub-Signature-256": "sha256=bad"}, body=body) is False


def test_whatsapp_webhook_challenge_uses_separate_verify_token() -> None:
    provider = provider_map()["whatsapp_cloud"]
    vault = InMemorySecretVault()
    _put(vault, provider, "verify_token", "verify-me")
    runtime = ProviderWebhookRuntime(vault)
    assert runtime.verify_challenge(provider=provider, tenant_id="tenant-a", business_id="business-a", mode="subscribe", verify_token="verify-me", challenge="12345") == "12345"
    assert runtime.verify_challenge(provider=provider, tenant_id="tenant-a", business_id="business-a", mode="subscribe", verify_token="wrong", challenge="12345") is None


def test_whatsapp_catalog_requires_vendor_specific_webhook_secrets() -> None:
    provider = provider_map()["whatsapp_cloud"]
    fields = {field.secret_name: field.secret_kind for field in provider.secret_fields}
    assert fields["access_token"] == "token"
    assert fields["phone_number_id"] == "config"
    assert fields["app_secret"] == "signing_secret"
    assert fields["verify_token"] == "config"


def test_every_messaging_provider_declares_truthful_inbound_mode() -> None:
    providers = provider_map()
    expected = {"telegram": "poll_or_webhook", "email": "mailbox_or_provider_webhook", "web_chat": "direct_ingress"}
    for channel, provider_key in MESSAGING_CHANNEL_PROVIDER_KEYS.items():
        binding = describe_provider_messaging_binding(providers[provider_key])
        assert binding is not None
        assert binding.inbound_mode == expected.get(channel, "provider_webhook")
    assert all(describe_provider_messaging_binding(providers[key]).inbound_mode == "provider_webhook" for key in BRIDGE_MESSAGING_PROVIDER_KEYS)


def test_meta_messaging_webhooks_support_native_hmac_and_challenge() -> None:
    providers = provider_map()
    body = b'{"object":"page","entry":[]}'
    for provider_key in ("instagram_messaging", "messenger_messaging"):
        provider = providers[provider_key]
        fields = {field.secret_name: field for field in provider.secret_fields}
        assert fields["app_secret"].secret_kind == "signing_secret" and fields["app_secret"].required is False
        assert fields["verify_token"].secret_kind == "config" and fields["verify_token"].required is False
        vault = InMemorySecretVault()
        _put(vault, provider, "app_secret", "meta-secret")
        _put(vault, provider, "verify_token", "verify-meta")
        runtime = ProviderWebhookRuntime(vault)
        signature = "sha256=" + hmac.new(b"meta-secret", body, hashlib.sha256).hexdigest()
        assert runtime.describe(provider).verification_kind == "hmac_sha256_hex"
        assert runtime.verify(provider=provider, tenant_id="tenant-a", business_id="business-a", headers={"X-Hub-Signature-256": signature}, body=body) is True
        assert runtime.verify_challenge(provider=provider, tenant_id="tenant-a", business_id="business-a", mode="subscribe", verify_token="verify-meta", challenge="42") == "42"


def test_meta_native_secret_prevents_shared_bridge_bypass() -> None:
    provider = provider_map()["instagram_messaging"]
    vault = InMemorySecretVault()
    _put(vault, provider, "webhook_secret", "bridge-secret")
    runtime = ProviderWebhookRuntime(vault)
    body = b'{"object":"instagram"}'
    assert runtime.verify(provider=provider, tenant_id="tenant-a", business_id="business-a", headers={"X-BusinessAIOS-Webhook-Secret": "bridge-secret"}, body=body) is True
    _put(vault, provider, "app_secret", "native-secret")
    assert runtime.verify(provider=provider, tenant_id="tenant-a", business_id="business-a", headers={"X-BusinessAIOS-Webhook-Secret": "bridge-secret"}, body=body) is False
