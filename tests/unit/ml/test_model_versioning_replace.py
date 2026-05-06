from __future__ import annotations

import pytest

from ml.training.model_versioning import ModelVersioning


def test_model_versioning_requires_explicit_replace_for_drift() -> None:
    versioning = ModelVersioning()
    versioning.set('model', 'v1')
    with pytest.raises(ValueError):
        versioning.set('model', 'v2')
    versioning.replace('model', 'v2')
    assert versioning.get('model') == 'v2'
