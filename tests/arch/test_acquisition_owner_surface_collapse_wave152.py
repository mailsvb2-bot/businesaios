from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding='utf-8')


def test_acquisition_boundary_modules_use_package_root() -> None:
    relpaths = [
        'acquisition/headless_entrypoint.py',
        'acquisition/request_adapter.py',
        'headless/acquisition_execution.py',
        'presentation/acquisition_view_model.py',
        'advisory/acquisition_recommendation_builder.py',
        'advisory/acquisition_result_projection.py',
    ]
    expectations = {
        'acquisition/headless_entrypoint.py': 'from acquisition import (',
        'acquisition/request_adapter.py': 'from acquisition import AcquisitionFeasibilityRequest, FunnelStage',
        'headless/acquisition_execution.py': 'from acquisition import AcquisitionFeasibilityRequest',
        'presentation/acquisition_view_model.py': 'from acquisition import AcquisitionFeasibilityResult',
        'advisory/acquisition_recommendation_builder.py': 'from acquisition import AcquisitionFeasibilityResult',
        'advisory/acquisition_result_projection.py': 'from acquisition import AcquisitionFeasibilityResult',
    }
    for relpath in relpaths:
        content = _read(relpath)
        assert expectations[relpath] in content, relpath


def test_advisory_package_root_marks_owner_surface() -> None:
    content = _read('advisory/__init__.py')
    assert 'CANON_ADVISORY_OWNER_SURFACE = True' in content
