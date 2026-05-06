from __future__ import annotations

FORBIDDEN_KEYS = (
    "winner",
    "winning_creative",
    "final_decision",
    "forced_action",
    "executor_command",
    "candidate_ids",
    "allowed_candidates",
    "filtered_candidates",
    "selected_candidate",
    "auto_selected",
    "narrowed_candidates",
    "best_candidate",
)

FORBIDDEN_METHOD_FRAGMENTS = (
    "choose_winner",
    "select_winner",
    "auto_select",
    "filter_action_space",
    "narrow_action_space",
    "execute_action",
    "commit_final_decision",
)


def _flatten_dict_keys(payload: object) -> tuple[str, ...]:
    found: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, inner in value.items():
                found.append(str(key))
                walk(inner)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                walk(item)

    walk(payload)
    return tuple(found)


def _has_forbidden_keys(payload: object) -> tuple[str, ...]:
    keys = _flatten_dict_keys(payload)
    matched = [key for key in keys if key in FORBIDDEN_KEYS]
    return tuple(sorted(set(matched)))


def _public_method_names(obj: object) -> tuple[str, ...]:
    names: list[str] = []
    for name in dir(obj):
        if name.startswith("_"):
            continue
        attr = getattr(obj, name)
        if callable(attr):
            names.append(name)
    return tuple(sorted(names))


def _has_forbidden_methods(obj: object) -> tuple[str, ...]:
    names = _public_method_names(obj)
    matched: list[str] = []
    for name in names:
        for fragment in FORBIDDEN_METHOD_FRAGMENTS:
            if fragment in name:
                matched.append(name)
    return tuple(sorted(set(matched)))


def test_autonomy_advisor_packet_has_no_hidden_selection_fields() -> None:
    from runtime.runtime_boot import boot_runtime
    from runtime.service_names import RuntimeServiceName

    registry = boot_runtime()
    advisor = registry.get(RuntimeServiceName.AUTONOMY_ADVISOR)
    packet = advisor.build_packet(
        market_snapshot=_fake_market_snapshot(),
        ranked_creatives=_fake_ranked_creatives(),
        architecture_global_stability=0.8,
        flow_turbulence=0.2,
    )
    forbidden = _has_forbidden_keys(packet.__dict__ if hasattr(packet, "__dict__") else packet)
    assert not forbidden, f"forbidden keys found in advisory packet: {forbidden}"


def test_recommendation_packet_has_no_narrowing_fields() -> None:
    from application.world_state.recommendation_packet_builder import build_recommendation_packet
    from contracts.decisioning.world_state_contract import WorldStateContract

    packet = build_recommendation_packet(
        packet_id="p1",
        world_state=WorldStateContract(
            state_id="s1",
            generated_at_ms=1,
            user_state={"intent": 0.6},
            market_state={"global_macro_score": 0.5},
            creative_state={"top_expected_value_score": 0.4},
            architecture_state={"global_stability": 0.8},
            structure_state={"curvature": 0.2},
            flow_state={"turbulence": 0.1},
            diffusion_state={"viral_potential": 0.3},
            economics_state={"portfolio_roi_mean": 0.2},
            reward_state={"scalarized_value": 0.4},
            advisory_flags={"packet_name": "advisory_v1"},
            notes=(),
        ),
        recommendations=(
            {
                "kind": "autonomy_advisory",
                "phase": "scale",
                "expected_value_score": 0.3,
                "downside_envelope": 0.2,
            },
        ),
        explanation_lines=("ok",),
    )
    forbidden = _has_forbidden_keys(packet.as_dict())
    assert not forbidden, f"forbidden keys found in recommendation packet: {forbidden}"


def test_decision_input_enrichment_has_no_hidden_selection_fields() -> None:
    from contracts.decisioning.decision_envelope_contract import DecisionEnvelopeContract
    from contracts.decisioning.decision_input_contract import DecisionInputContract
    from application.decisioning.decision_core_input_bridge import build_decision_core_enrichment

    enrichment = build_decision_core_enrichment(
        DecisionInputContract(
            envelope=DecisionEnvelopeContract(
                packet_id="p1",
                world_state_features={"reward.scalarized_value": 0.4},
                advisory_features={"advisory.scale_pressure": 0.8},
                explanation_lines=("safe",),
                metadata={},
            )
        )
    )
    forbidden = _has_forbidden_keys(enrichment)
    assert not forbidden, f"forbidden keys found in decision enrichment: {forbidden}"


def test_behavioral_services_do_not_expose_forbidden_decision_methods() -> None:
    from runtime.runtime_boot import boot_runtime
    from runtime.service_names import RuntimeServiceName

    registry = boot_runtime()
    service_names = (
        RuntimeServiceName.MARKET_WATCH,
        RuntimeServiceName.CREATIVE_INTELLIGENCE,
        RuntimeServiceName.AUTONOMY_ADVISOR,
        RuntimeServiceName.WORLD_STATE_INTEGRATION,
        RuntimeServiceName.DECISION_INPUT_SERVICE,
    )
    violations: dict[str, tuple[str, ...]] = {}
    for service_name in service_names:
        service = registry.get(service_name)
        forbidden_methods = _has_forbidden_methods(service)
        if forbidden_methods:
            violations[service_name] = forbidden_methods
    assert not violations, f"forbidden public methods detected: {violations}"


def test_advisory_features_are_soft_signals_not_candidate_control() -> None:
    from application.decision_input.advisory_feature_extractor import extract_advisory_features

    features = extract_advisory_features(
        (
            {
                "kind": "autonomy_advisory",
                "phase": "scale",
                "expected_value_score": 0.6,
                "downside_envelope": 0.2,
            },
            {
                "kind": "autonomy_advisory",
                "phase": "hold",
                "expected_value_score": 0.1,
                "downside_envelope": 0.3,
            },
        )
    )
    assert "advisory.scale_pressure" in features
    assert "advisory.mean_expected_value" in features
    forbidden = _has_forbidden_keys(features)
    assert not forbidden, f"forbidden keys found in advisory features: {forbidden}"


def _fake_market_snapshot():
    from runtime.market.market_snapshot import MarketSnapshot

    return MarketSnapshot(
        global_macro_score=0.6,
        global_micro_score=0.55,
        global_competitive_shift=0.2,
        segment_states=(),
    )


def _fake_ranked_creatives():
    from core.creative_intelligence.models import (
        CreativeIntelligenceSnapshot,
        CreativePnLSnapshot,
        ExperimentConfidenceSnapshot,
        IncrementalitySnapshot,
    )

    return (
        CreativeIntelligenceSnapshot(
            creative_id="creative_a",
            pnl=CreativePnLSnapshot(
                creative_id="creative_a",
                attributed_revenue=500.0,
                total_cost=200.0,
                contribution_profit=300.0,
                contribution_margin_ratio=0.6,
                roi=1.5,
            ),
            incrementality=IncrementalitySnapshot(
                creative_id="creative_a",
                estimated_effect=0.14,
                confidence_score=0.8,
                downside_risk=0.2,
                method="dr",
            ),
            experiment_confidence=ExperimentConfidenceSnapshot(
                creative_id="creative_a",
                uplift=0.12,
                p_value=0.03,
                confidence_score=0.97,
                rollout_readiness=0.85,
            ),
            expected_value_score=0.45,
            downside_envelope=0.2,
            portfolio_rank_score=0.5,
            explanations=(),
        ),
    )
