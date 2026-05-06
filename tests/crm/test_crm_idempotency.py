import pytest
from crm.upsert.crm_idempotency_policy import CrmIdempotencyPolicy


def test_idempotency_key_is_required():
    with pytest.raises(ValueError):
        CrmIdempotencyPolicy().ensure('')
