import json

from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def _put(vault, provider, business, name, value):
    ref = SecretRef(tenant_id="tenant-a", connector_id=provider.connector_id,
                    scope=business, secret_name=f"{provider.connector_id}.{name}")
    vault.put(SecretRecord(ref=ref, ciphertext=b"pending", source=SecretSource.CONNECTOR),
              plaintext=value.encode())


def test_max_group_requires_trusted_business_chat_binding(monkeypatch):
    monkeypatch.setenv("BAI_WEBHOOK_RECIPIENT_BINDING_STRICT", "1")
    provider = provider_map()["max_messaging"]
    vault = InMemorySecretVault()
    _put(vault, provider, "biz-a", "bot_id", "100100")
    runtime = ProviderWebhookRuntime(vault)
    event = {"update_type": "message_created", "message": {
        "recipient": {"chat_type": "chat", "chat_id": "777"},
        "sender": {"user_id": "12345", "is_bot": False}}}
    def check(business):
        return runtime._recipient_matches(
            provider=provider, tenant_id="tenant-a", business_id=business,
            body=json.dumps(event).encode())
    assert check("biz-a") is False
    _put(vault, provider, "biz-a", "chat_ids", "777,888")
    assert check("biz-a") is True
    assert check("biz-b") is False
    event["message"]["sender"]["user_id"] = "100100"
    assert check("biz-a") is False


def test_vk_group_binding_is_business_scoped(monkeypatch):
    monkeypatch.setenv("BAI_WEBHOOK_RECIPIENT_BINDING_STRICT", "1")
    provider = provider_map()["vk_messaging"]
    vault = InMemorySecretVault()
    _put(vault, provider, "biz-a", "group_id", "100")
    runtime = ProviderWebhookRuntime(vault)
    event = {"group_id": 100, "object": {"message": {"from_id": 12345}}}
    def check(biz):
        return runtime._recipient_matches(provider=provider, tenant_id="tenant-a",
                                           business_id=biz, body=json.dumps(event).encode())
    assert check("biz-a") and not check("biz-b")
    event["object"]["message"]["from_id"] = 100
    assert not check("biz-a")


def test_max_group_chat_binding_is_configurable_by_existing_provider_catalog():
    fields = provider_map()["max_messaging"].secret_fields
    assert any(field.secret_name == "chat_ids" and not field.required for field in fields)


def test_vk_negative_community_id_is_not_person(monkeypatch):
    monkeypatch.setenv("BAI_WEBHOOK_RECIPIENT_BINDING_STRICT", "1")
    provider = provider_map()["vk_messaging"]
    vault = InMemorySecretVault()
    _put(vault, provider, "biz-a", "group_id", "100")
    event = {"group_id": 100, "object": {"message": {"from_id": -100}}}
    assert not ProviderWebhookRuntime(vault)._recipient_matches(
        provider=provider, tenant_id="tenant-a", business_id="biz-a",
        body=json.dumps(event).encode())
