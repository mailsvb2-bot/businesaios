from observability.metric_counter import MetricCounter


def test_metric_counter_coerces_non_finite_values_to_zero() -> None:
    counter = MetricCounter()
    counter.observe('lead_events', float('inf'))
    counter.observe('lead_events', 'bad')
    counter.observe('lead_events', 2)
    assert counter.values['lead_events'] == 2.0
