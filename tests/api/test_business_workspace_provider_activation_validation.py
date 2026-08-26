from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from adapters.api.fastapi.business_workspace_provider_routes import _validated_activation_secrets
from application.business_autonomy.provider_truth_matrix import provider_truth_map


@pytest.mark.parametrize('provider_key', ('telegram_bot', 'vk_messaging', 'max_messaging'))
def test_activation_missing_required_credentials_fails_closed(provider_key: str) -> None:
    truth = provider_truth_map()[provider_key]
    assert truth.required_credentials

    with pytest.raises(HTTPException) as exc_info:
        _validated_activation_secrets(truth=truth, body={'secrets': {}})

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert exc_info.value.detail == 'provider_required_credentials_missing'


def test_activation_rejects_non_mapping_secret_payload() -> None:
    truth = provider_truth_map()['telegram_bot']

    with pytest.raises(HTTPException) as exc_info:
        _validated_activation_secrets(truth=truth, body={'secrets': ['not', 'a', 'mapping']})

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert exc_info.value.detail == 'provider_secrets_invalid'


@pytest.mark.parametrize('provider_key', ('telegram_bot', 'vk_messaging', 'max_messaging'))
def test_activation_accepts_complete_required_credentials(provider_key: str) -> None:
    truth = provider_truth_map()[provider_key]
    supplied = {name: f'smoke-{name}' for name in truth.required_credentials}

    assert _validated_activation_secrets(truth=truth, body={'secrets': supplied}) == supplied
