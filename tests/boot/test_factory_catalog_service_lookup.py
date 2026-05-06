from __future__ import annotations

import pytest

from boot.factories import FACTORY_SERVICE_NAMES, FACTORY_FUNCTIONS, get_factory_for_service
from runtime.errors import RuntimeConfigurationError
from runtime.service_names import RuntimeServiceName


def test_get_factory_for_service_uses_canonical_catalog_mapping() -> None:
    for service_name, factory_name in FACTORY_SERVICE_NAMES.items():
        assert get_factory_for_service(service_name) is FACTORY_FUNCTIONS[factory_name]


def test_get_factory_for_service_rejects_unknown_service() -> None:
    with pytest.raises(RuntimeConfigurationError):
        get_factory_for_service(RuntimeServiceName.DECISION_CORE)
