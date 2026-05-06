from __future__ import annotations

from dataclasses import dataclass

import pytest

from interfaces.api.fastapi_app_factory import create_fastapi_app
from interfaces.api.fastapi_dependencies import FastAPIDependencyContainer


@dataclass(frozen=True)
class _Boot:
    decision_application: object


def test_fastapi_app_factory_rejects_mismatched_boot_service() -> None:
    with pytest.raises(ValueError):
        create_fastapi_app(
            application_service=object(),
            dependency_container=FastAPIDependencyContainer(boot_result=_Boot(decision_application=object())),
        )
