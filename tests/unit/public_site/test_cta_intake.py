from __future__ import annotations

import json

from application.public_site.cta_intake import CTALandingIntakeService


def test_cta_intake_records_row_and_returns_ui_url(tmp_path):
    path = tmp_path / "pilot_applications.jsonl"
    service = CTALandingIntakeService(
        storage_path=str(path),
        app_base_url="https://app.businessaios.ru",
    )

    result = service.submit(payload={"email": "test@example.com", "intent": "demo"})

    assert result.intake_id.startswith("cta-")
    assert result.outcome == "intake_recorded"
    assert result.app_url.endswith(result.intake_id)

    rows = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row["intake_id"] == result.intake_id
    assert row["source"] == "public_landing_cta"


def test_cta_intake_status_lookup(tmp_path):
    path = tmp_path / "pilot_applications.jsonl"
    service = CTALandingIntakeService(storage_path=str(path))
    result = service.submit(payload={"email": "a@b.c"})

    found = service.get_status(intake_id=result.intake_id)
    assert found.found is True
    assert found.outcome == "intake_recorded"

    missing = service.get_status(intake_id="cta-missing")
    assert missing.found is False
    assert missing.outcome == "not_found"
