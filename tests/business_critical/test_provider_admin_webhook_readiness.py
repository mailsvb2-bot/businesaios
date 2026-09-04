from __future__ import annotations

from application.business_autonomy.provider_admin_contract import ProviderCredentialSubmission
from application.business_autonomy.provider_admin_service import ProviderAdminService
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from runtime.business_autonomy.provider_webhook_reconciliation import ProviderWebhookReconciler
from security.connector_secret_scope import ConnectorSecretScope
from security.secret_vault import InMemorySecretVault


class _Onboarding:
    def onboard(self, request):
        return type(
            'OnboardingResult', (), {'persistent_surfaces': ('evidence',), 'ready': True}
        )()


def _service(tmp_path) -> ProviderAdminService:
    return ProviderAdminService(
        onboarding_service=_Onboarding(),
        secret_vault=InMemorySecretVault(),
        connector_secret_scope=ConnectorSecretScope(),
        activation_store=FileProviderActivationStore(FileDistributedDocumentStore(tmp_path / 'docs')),
    )


def _telegram_submission() -> ProviderCredentialSubmission:
    return ProviderCredentialSubmission(
        tenant_id='tenant-a',
        business_id='business-a',
        provider_key='telegram_bot',
        ownership_key='owner:business-a',
        requested_by='tester',
        external_ref='telegram://business-a',
        metadata={'verified_owner': True},
        secrets={'bot_token': '123:BOT'},
    )


def test_provider_admin_marks_connection_not_ready_when_reconciliation_fails(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://api.businessaios.ru')
    monkeypatch.setattr(
        ProviderWebhookReconciler,
        'reconcile',
        lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError('provider rejected')),
    )
    status = _service(tmp_path).activate_provider(_telegram_submission())
    assert status.connected is False
    assert status.onboarding_ready is False
    assert status.metadata['webhook_reconciliation']['status'] == 'failed'


def test_provider_admin_preserves_dev_connection_but_reports_manual_webhook_work(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv('PUBLIC_BASE_URL', raising=False)
    status = _service(tmp_path).activate_provider(_telegram_submission())
    assert status.connected is True
    assert status.onboarding_ready is True
    reconciliation = status.metadata['webhook_reconciliation']
    assert reconciliation['status'] == 'manual_required'
    assert reconciliation['ready'] is False
    assert reconciliation['reason'] == 'public_base_url_not_configured'
