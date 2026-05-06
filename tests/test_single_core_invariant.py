import pathlib


FORBIDDEN = [
    "core/decision/envelope.py",
    "runtime/purity",
    "purity_executor.py",
    "self_driving_contour.py",
]


def test_single_core():
    repo = pathlib.Path(__file__).resolve().parents[1]

    for pattern in FORBIDDEN:
        assert not list(repo.rglob(pattern)), f"Forbidden artifact: {pattern}"
