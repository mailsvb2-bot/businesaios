from __future__ import annotations

import pytest

from ml.training.model_versioning import ModelVersioning


def test_model_versioning_rejects_empty_names() -> None:
    with pytest.raises(ValueError):
        ModelVersioning().set('', 'v1')
