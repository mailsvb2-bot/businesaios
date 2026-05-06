from __future__ import annotations

import pytest

from app.web.components import AutopilotButton
from app.web.pages import Autopilot
from app.web.pages import Dashboard
from app.web.payload_builder import KindedPayloadBuilder


@pytest.mark.parametrize(
    ('builder', 'expected_kind'),
    [
        (Autopilot(), 'autopilot'),
        (Dashboard(), 'dashboard'),
        (AutopilotButton(), 'autopilot_button'),
    ],
)
def test_kinded_payload_builder_preserves_kind_and_copies_payload(builder, expected_kind):
    payload = {'x': 1}
    result = builder.build(payload)

    assert result == {'kind': expected_kind, 'payload': {'x': 1}}
    assert result['payload'] is not payload


def test_kinded_payload_builder_rejects_empty_kind():
    with pytest.raises(TypeError):
        class BrokenBuilder(KindedPayloadBuilder):
            KIND = '   '
