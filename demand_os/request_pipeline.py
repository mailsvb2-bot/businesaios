from __future__ import annotations

from contracts.demand import DemandFlowBundle
from observability.demand import emit_demand_events as emit_demand_event


class DemandRequestPipeline:
    def __init__(self, *, capture, intent_builder, business_directory, state_builder, gravity_model, match_engine, router, decision_bridge, delivery_dispatcher, snapshot, event_log: object | None = None) -> None:
        self._capture = capture
        self._intent = intent_builder
        self._directory = business_directory
        self._state_builder = state_builder
        self._gravity = gravity_model
        self._match_engine = match_engine
        self._router = router
        self._decision_bridge = decision_bridge
        self._delivery = delivery_dispatcher
        self._snapshot = snapshot
        self._event_log = event_log

    def _list_supply_profiles(self):
        lister = getattr(self._directory, 'list_profiles', None)
        if not callable(lister):
            raise ValueError('business_directory must provide list_profiles()')
        seen: set[str] = set()
        ordered = []
        for profile in tuple(lister() or ()):
            business_id = str(getattr(profile, 'business_id', '') or '').strip()
            if not business_id or business_id in seen:
                continue
            seen.add(business_id)
            ordered.append(profile)
        return tuple(ordered)

    def _build_live_states(self, profiles):
        live_states = []
        seen: set[str] = set()
        for profile in profiles:
            state = self._state_builder.build(profile.business_id)
            state_business_id = str(getattr(state, 'business_id', '') or '').strip()
            if state_business_id != str(profile.business_id):
                raise ValueError('business_live_state_builder returned mismatched business_id')
            if state_business_id in seen:
                continue
            seen.add(state_business_id)
            live_states.append(state)
        return tuple(live_states)

    def _gravity_snapshot(self, *, intent, profiles, live_states, optimizer) -> dict[str, object]:
        states_by_business = {state.business_id: state for state in live_states}
        vectors = {}
        for profile in profiles:
            live_state = states_by_business.get(profile.business_id)
            if live_state is None:
                continue
            vectors[profile.business_id] = self._gravity.vector_for(intent=intent, profile=profile, live_state=live_state)
        return {'vectors': vectors, 'policy_state': optimizer.current_state()}

    def _validate_stage_alignment(self, *, request, match_bundle, routing_preparation) -> None:
        request_id = str(getattr(request, 'request_id', '') or '')
        if not request_id:
            raise ValueError('captured request must provide request_id')
        match_request_id = str(getattr(match_bundle, 'request_id', '') or '')
        if match_request_id != request_id:
            raise ValueError('match bundle request_id must match captured request')
        routing_request_id = str(routing_preparation.get('request_id') or '')
        if routing_request_id != request_id:
            raise ValueError('routing preparation request_id must match captured request')
        trace = dict(routing_preparation.get('trace') or {})
        trace_request_id = str(trace.get('request_id') or '')
        if trace_request_id and trace_request_id != request_id:
            raise ValueError('routing trace request_id must match captured request')

    def process(self, *, raw_event: dict[str, object], optimizer) -> DemandFlowBundle:
        request = self._capture.capture(raw_event)
        self._snapshot.request_count += 1
        self._snapshot.last_request_id = request.request_id
        emit_demand_event(self._event_log, 'request_captured', {'request_id': request.request_id, 'customer_id': request.customer_id})
        intent = self._intent.build(request)
        supply_profiles = self._list_supply_profiles()
        live_states = self._build_live_states(supply_profiles)
        gravity_snapshot = self._gravity_snapshot(intent=intent, profiles=supply_profiles, live_states=live_states, optimizer=optimizer)
        match_bundle = self._match_engine.build_bundle(
            request=request,
            intent=intent,
            profiles=supply_profiles,
            live_states=live_states,
            gravity_snapshot=gravity_snapshot,
        )
        routing_preparation = self._router.prepare(request=request, intent=intent, match_bundle=match_bundle)
        self._validate_stage_alignment(request=request, match_bundle=match_bundle, routing_preparation=routing_preparation)
        decision = self._decision_bridge.evaluate(request=request, routing_preparation=routing_preparation)
        self._snapshot.decision_count += 1
        if decision.selected_business_id:
            self._snapshot.last_business_id = decision.selected_business_id
        delivery = self._delivery.dispatch(request=request, decision=decision)
        self._snapshot.delivery_count += int(bool(delivery))
        emit_demand_event(self._event_log, 'request_processed', {
            'request_id': request.request_id,
            'customer_id': request.customer_id,
            'business_id': decision.selected_business_id or '',
            'requires_manual_review': bool(getattr(decision, 'requires_manual_review', False)),
        })
        return DemandFlowBundle(
            request=request,
            intent=intent,
            supply_profiles=supply_profiles,
            live_states=live_states,
            gravity_snapshot=gravity_snapshot,
            match_bundle=match_bundle,
            routing_preparation=routing_preparation,
            decision=decision,
            delivery=delivery,
        )
