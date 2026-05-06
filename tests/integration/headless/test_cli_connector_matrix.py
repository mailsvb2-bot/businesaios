from __future__ import annotations

import json

from interfaces.cli.headless_product import main


def test_cli_connector_matrix_prints_honest_registry_truth(capsys) -> None:
    code = main(["connector-matrix", "--domain", "reviews", "--connector", "google_reviews"])
    assert code == 0
    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    row = output[0]
    assert row["connector_name"] == "google_reviews"
    assert row["implemented"] is True
    assert row["production_ready"] is False
