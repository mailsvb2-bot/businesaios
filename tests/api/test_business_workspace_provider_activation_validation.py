from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from adapters.api.fastapi.business_workspace_provider_routes import _validated_activation_secrets
from application.business_autonomy.provider_truth_matrix import provider_truth_map


TRUTH_ROWS = provider_truth_map()
REQUIRED_CREDENTIAL_PROVIDER_KEYS = tuple(
    sorted(provider_key for provider_key, truth in TRUTH_ROWS.items() if truth.required_credentials)
)
NO_REQUIRED_CREDENTIAL_PROVIDER_KEYS = tuple(
    sorted(provider_key for provider_key, truth in TRUTH_ROWS.items() if not truth.required_credentials)
)


def _complete_secrets(provider_key: str) -> dict[str, str]:
    truth = TRUTH_ROWS[provider_key]
    return {name: f"smoke-{provider_key}-{name}" for name in truth.required_credentials}


@pytest.mark.parametrize("provider_key", REQUIRED_CREDENTIAL_PROVIDER_KEYS)
def test_activation_missing_all_required_credentials_fails_closed(provider_key: str) -> None:
    truth = TRUTH_ROWS[provider_key]

    with pytest.raises(HTTPException) as exc_info:
        _validated_activation_secrets(truth=truth, body={"secrets": {}})

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert exc_info.value.detail == "provider_required_credentials_missing"


@pytest.mark.parametrize("provider_key", REQUIRED_CREDENTIAL_PROVIDER_KEYS)
def test_activation_missing_each_required_credential_fails_closed(provider_key: str) -> None:
    truth = TRUTH_ROWS[provider_key]
    supplied = _complete_secrets(provider_key)

    for missing_name in truth.required_credentials:
        incomplete = {name: value for name, value in supplied.items() if name != missing_name}
        with pytest.raises(HTTPException) as exc_info:
            _validated_activation_secrets(truth=truth, body={"secrets": incomplete})
        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert exc_info.value.detail == "provider_required_credentials_missing"


def test_activation_rejects_non_mapping_secret_payload() -> None:
    truth = next(iter(TRUTH_ROWS.values()))

    with pytest.raises(HTTPException) as exc_info:
        _validated_activation_secrets(truth=truth, body={"secrets": ["not", "a", "mapping"]})

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert exc_info.value.detail == "provider_secrets_invalid"


@pytest.mark.parametrize("provider_key", REQUIRED_CREDENTIAL_PROVIDER_KEYS)
def test_activation_accepts_complete_required_credentials(provider_key: str) -> None:
    truth = TRUTH_ROWS[provider_key]
    supplied = _complete_secrets(provider_key)

    assert _validated_activation_secrets(truth=truth, body={"secrets": supplied}) == supplied


@pytest.mark.parametrize("provider_key", NO_REQUIRED_CREDENTIAL_PROVIDER_KEYS)
def test_activation_accepts_empty_secrets_when_provider_requires_none(provider_key: str) -> None:
    truth = TRUTH_ROWS[provider_key]

    assert _validated_activation_secrets(truth=truth, body={"secrets": {}}) == {}


def test_truth_matrix_exercises_both_credential_contract_shapes() -> None:
    assert REQUIRED_CREDENTIAL_PROVIDER_KEYS
    assert NO_REQUIRED_CREDENTIAL_PROVIDER_KEYS
    assert set(REQUIRED_CREDENTIAL_PROVIDER_KEYS).isdisjoint(NO_REQUIRED_CREDENTIAL_PROVIDER_KEYS)
    assert set(REQUIRED_CREDENTIAL_PROVIDER_KEYS) | set(NO_REQUIRED_CREDENTIAL_PROVIDER_KEYS) == set(TRUTH_ROWS)
