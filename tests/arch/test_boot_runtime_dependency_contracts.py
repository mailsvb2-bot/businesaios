from __future__ import annotations

import pytest

from boot.registrations._shared import _validate_dependency_contract
from runtime.service_names import RuntimeServiceName


def test_dependency_contract_rejects_undeclared_runtime_service() -> None:
    with pytest.raises(ValueError):
        _validate_dependency_contract(
            dependencies=(RuntimeServiceName.OBSERVABILITY,),
            dependency_map={'observability': RuntimeServiceName.DECISION_INPUT_SERVICE},
        )


def test_dependency_contract_rejects_duplicate_service_mapping() -> None:
    with pytest.raises(ValueError):
        _validate_dependency_contract(
            dependencies=(RuntimeServiceName.OBSERVABILITY, RuntimeServiceName.DECISION_INPUT_SERVICE),
            dependency_map={
                'observability': RuntimeServiceName.OBSERVABILITY,
                'other': RuntimeServiceName.OBSERVABILITY,
            },
        )
