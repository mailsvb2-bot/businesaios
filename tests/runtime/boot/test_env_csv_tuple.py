import pytest

from runtime.boot.system_builder import _env_csv_tuple


def test_env_csv_tuple_parses_and_normalizes(monkeypatch):
    monkeypatch.delenv("XCSV", raising=False)
    assert _env_csv_tuple("XCSV", ("a", "b")) == ("a", "b")

    monkeypatch.setenv("XCSV", " marketing, bulk ,analytics ,,  ")
    assert _env_csv_tuple("XCSV", ("x",)) == ("marketing", "bulk", "analytics")

    monkeypatch.setenv("XCSV", "   ")
    assert _env_csv_tuple("XCSV", ("z",)) == ("z",)

    monkeypatch.setenv("XCSV", ",,")
    assert _env_csv_tuple("XCSV", ("z",)) == ("z",)
