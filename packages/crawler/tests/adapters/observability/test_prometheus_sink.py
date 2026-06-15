"""Sink Prometheus : inc/set/observe sur un CollectorRegistry jetable (get_sample_value)."""

from prometheus_client import CollectorRegistry

from emule_indexer.adapters.observability.prometheus_sink import PrometheusSink
from emule_indexer.domain.observability.policy import MetricInstruction, MetricName


def test_counter_inc_with_label() -> None:
    registry = CollectorRegistry()
    sink = PrometheusSink(registry)
    sink.apply(MetricInstruction(MetricName.OBSERVATIONS, "inc", (("network", "ed2k"),)))
    sink.apply(MetricInstruction(MetricName.OBSERVATIONS, "inc", (("network", "ed2k"),)))
    # counter exposé AVEC le suffixe _total ajouté par prometheus_client
    assert registry.get_sample_value("emule_observations_total", {"network": "ed2k"}) == 2.0


def test_counter_inc_no_label() -> None:
    registry = CollectorRegistry()
    PrometheusSink(registry).apply(MetricInstruction(MetricName.DOWNLOADS_COMPLETED, "inc"))
    assert registry.get_sample_value("emule_downloads_completed_total") == 1.0


def test_gauge_set_with_label() -> None:
    registry = CollectorRegistry()
    PrometheusSink(registry).apply(
        MetricInstruction(MetricName.CONNECTED_INSTANCES, "set", (("network", "kad"),), 3.0)
    )
    assert registry.get_sample_value("emule_connected_instances", {"network": "kad"}) == 3.0


def test_gauge_set_no_label() -> None:
    registry = CollectorRegistry()
    PrometheusSink(registry).apply(MetricInstruction(MetricName.CRAWLER_UP, "set", (), 1.0))
    assert registry.get_sample_value("emule_crawler_up") == 1.0


def test_histogram_observe() -> None:
    registry = CollectorRegistry()
    PrometheusSink(registry).apply(
        MetricInstruction(MetricName.SEARCH_CYCLE_DURATION, "observe", (), 2.5)
    )
    assert registry.get_sample_value("emule_search_cycle_duration_seconds_count") == 1.0
    assert registry.get_sample_value("emule_search_cycle_duration_seconds_sum") == 2.5
