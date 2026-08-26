import pytest
from fastapi import HTTPException, status
from adapters.api.fastapi.business_workspace_provider_routes import _validated_activation_secrets
from application.business_autonomy.provider_truth_matrix import provider_truth_map
TRUTH_ROWS = provider_truth_map()
@pytest.mark.parametrize("provider_key", sorted(TRUTH_ROWS))
def test_activation_secret_contract_matches_truth_matrix(provider_key: str) -> None:
    truth = TRUTH_ROWS[provider_key]
    supplied = {name: f"smoke-{provider_key}-{name}" for name in truth.required_credentials}
    if truth.required_credentials:
        missing_cases = ({}, *({k: v for k, v in supplied.items() if k != name} for name in truth.required_credentials))
        for incomplete in missing_cases:
            with pytest.raises(HTTPException) as exc_info:
                _validated_activation_secrets(truth=truth, body={"secrets": incomplete})
            assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            assert exc_info.value.detail == "provider_required_credentials_missing"
    assert _validated_activation_secrets(truth=truth, body={"secrets": supplied}) == supplied

def test_activation_rejects_non_mapping_secret_payload() -> None:
    truth = next(iter(TRUTH_ROWS.values()))
    with pytest.raises(HTTPException) as exc_info:
        _validated_activation_secrets(truth=truth, body={"secrets": ["not", "a", "mapping"]})
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert exc_info.value.detail == "provider_secrets_invalid"
