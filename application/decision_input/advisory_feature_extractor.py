from __future__ import annotations


def extract_advisory_features(
    recommendations: tuple[dict[str, object], ...],
) -> dict[str, float]:
    if not recommendations:
        return {
            "advisory.count": 0.0,
            "advisory.scale_pressure": 0.0,
            "advisory.launch_pressure": 0.0,
            "advisory.stop_pressure": 0.0,
            "advisory.reallocate_pressure": 0.0,
            "advisory.mean_expected_value": 0.0,
            "advisory.mean_downside": 0.0,
        }

    phase_counts = {
        "scale": 0.0,
        "launch": 0.0,
        "stop": 0.0,
        "reallocate": 0.0,
        "hold": 0.0,
        "select": 0.0,
    }
    ev_sum = 0.0
    downside_sum = 0.0

    for item in recommendations:
        phase = str(item.get("phase") or item.get("reallocation_bias") or "hold")
        if phase in phase_counts:
            phase_counts[phase] += 1.0
        ev_sum += float(item.get("expected_value_score", 0.0))
        downside_sum += float(item.get("downside_envelope", 0.0))

    count = float(len(recommendations))
    return {
        "advisory.count": count,
        "advisory.scale_pressure": phase_counts["scale"] / count,
        "advisory.launch_pressure": phase_counts["launch"] / count,
        "advisory.stop_pressure": phase_counts["stop"] / count,
        "advisory.reallocate_pressure": phase_counts["reallocate"] / count,
        "advisory.mean_expected_value": ev_sum / count,
        "advisory.mean_downside": downside_sum / count,
    }
