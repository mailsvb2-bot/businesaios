from __future__ import annotations

import math

from execution.market_intelligence_data_quality import (
    DataQualityGuard,
    DataQualityReport,
    _clean_text,
    _fingerprint,
    _normalize_url,
    _normalized_float,
    _normalized_int,
    _safe_dict,
)


def test_helpers_are_stable_and_do_not_collapse_delimiter_boundaries():
    assert _safe_dict({"a": 1}) == {"a": 1}
    assert _safe_dict([("a", 1)]) == {}
    assert _clean_text("  hello\n world  ") == "hello world"
    assert _normalize_url(None) == ""
    assert _normalize_url("ftp://EXAMPLE.test/a#fragment") == "ftp://EXAMPLE.test/a#fragment"
    assert _normalize_url(" HTTPS://EXAMPLE.test/A?q=1#fragment ") == "https://example.test/A?q=1"

    left = {"record_id": "a|b", "external_id": "c"}
    right = {"record_id": "a", "external_id": "b|c"}
    assert _fingerprint(left) != _fingerprint(right)
    assert _fingerprint({"other": 1}) == _fingerprint({"other": 1})
    assert _fingerprint({"other": 1}) != _fingerprint({"other": 2})


def test_numeric_normalizers_preserve_non_finite_values_for_anomaly_detection():
    assert _normalized_float("bad") == "bad"
    assert _normalized_float(-2) == 0.0
    assert _normalized_float(8, upper=5.0) == 5.0
    assert math.isnan(_normalized_float(float("nan")))
    assert _normalized_float(float("inf")) == float("inf")

    assert _normalized_int("bad") == "bad"
    assert _normalized_int(-2) == 0
    assert _normalized_int("3.9") == 3
    assert _normalized_int(float("inf")) == float("inf")


def test_report_and_normalization_contract():
    report = DataQualityReport(5, 2, 1, 2, 1)
    assert report.as_dict() == {
        "total_rows": 5,
        "kept_rows": 2,
        "dropped_duplicates": 1,
        "dropped_noise": 2,
        "anomaly_rows": 1,
    }

    normalized = DataQualityGuard()._normalize(
        {
            7: "value",
            "title": "  Useful\n product ",
            "name": None,
            "headline": " Head ",
            "description": " Body ",
            "copy": " Copy ",
            "provider": " Provider ",
            "source_family": " Family ",
            "record_id": " ID ",
            "external_id": " External ",
            "id": " Local ",
            "url": "HTTP://EXAMPLE.TEST/path#frag",
            "rating": "7",
            "price": "-2",
            "engagement": "bad",
            "impressions": "12.5",
            "review_count": "4.9",
        }
    )
    assert normalized == {
        "7": "value",
        "title": "Useful product",
        "name": "",
        "headline": "Head",
        "description": "Body",
        "copy": "Copy",
        "provider": "Provider",
        "source_family": "Family",
        "record_id": "ID",
        "external_id": "External",
        "id": "Local",
        "url": "http://example.test/path",
        "rating": 5.0,
        "price": 0.0,
        "engagement": "bad",
        "impressions": 12.5,
        "review_count": 4,
    }


def test_noise_classifier_covers_all_rejection_paths_and_url_exception():
    guard = DataQualityGuard()
    assert guard._is_noise({})
    assert guard._is_noise({"title": "abc"})
    assert guard._is_noise({"title": "null"})
    assert guard._is_noise({"title": "buy now buy now buy now"})
    assert not guard._is_noise({"title": "https://example.test buy now buy now buy now"})
    assert guard._is_noise({"title": "heyyyyyy"})
    assert guard._is_noise({"title": "word word word"})
    assert not guard._is_noise({"title": "longwords longwords"})
    assert guard._is_noise({"title": "1234567890"})
    assert not guard._is_noise({"title": "Model 123 works"})


def test_anomaly_classifier_covers_empty_invalid_finite_large_and_nonfinite():
    guard = DataQualityGuard()
    assert not guard._is_anomaly({})
    assert not guard._is_anomaly({"price": None, "rating": "bad"})
    assert not guard._is_anomaly({"price": 10, "rating": 4.5})
    assert guard._is_anomaly({"impressions": 1_000_001})
    assert guard._is_anomaly({"review_count": float("inf")})


def test_process_drops_noise_and_duplicates_but_keeps_distinct_delimited_ids():
    rows = [
        None,
        {"title": "Useful product", "record_id": "same", "price": float("nan")},
        {"title": "Useful product", "record_id": "same", "price": 12},
        {"title": "First useful", "record_id": "a|b", "external_id": "c"},
        {"title": "Second useful", "record_id": "a", "external_id": "b|c"},
        {"title": "Normal useful", "record_id": "normal", "price": 9},
    ]
    kept, report = DataQualityGuard().process(rows)  # type: ignore[arg-type]

    assert report == DataQualityReport(
        total_rows=6,
        kept_rows=4,
        dropped_duplicates=1,
        dropped_noise=1,
        anomaly_rows=1,
    )
    assert kept[0]["quality_flag"] == "anomaly"
    assert {item["record_id"] for item in kept} == {"same", "a|b", "a", "normal"}
