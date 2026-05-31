from runtime.bootstrap.crm_connector_boot import _build_token_store, build_crm_connector_registry
from security.secret_vault import InMemorySecretVault


class _TokenStore:
    def load(self, *, provider_key: str, secret_ref: str):
        return None

    def save(self, *, provider_key: str, secret_ref: str, token) -> None:
        raise AssertionError("save should not be called")

    def delete(self, *, provider_key: str, secret_ref: str) -> None:
        raise AssertionError("delete should not be called")


def test_connector_boot_accepts_injected_token_store() -> None:
    registry = build_crm_connector_registry(token_store=_TokenStore(), vault=InMemorySecretVault())
    assert registry.get("hubspot") is not None
    assert registry.get("pipedrive") is not None




def test_connector_boot_prefers_vault_backed_store_when_vault_is_injected() -> None:
    vault = InMemorySecretVault()
    store = _build_token_store(vault=vault)
    assert getattr(store, 'vault', None) is vault
