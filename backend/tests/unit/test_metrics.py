"""Unit tests for app/metrics.py — Prometheus counters/gauges."""
from prometheus_client import Counter, Gauge, generate_latest

from app.metrics import ACTIVE_EVENTS, CACHE_OPERATIONS, REPORTS_SUBMITTED


def test_reports_submitted_is_counter():
    assert isinstance(REPORTS_SUBMITTED, Counter)


def test_active_events_is_gauge():
    assert isinstance(ACTIVE_EVENTS, Gauge)


def test_cache_operations_is_counter():
    assert isinstance(CACHE_OPERATIONS, Counter)


def test_reports_submitted_inc_with_labels_does_not_raise():
    REPORTS_SUBMITTED.labels(status="safe", facility="TestFab").inc()
    REPORTS_SUBMITTED.labels(status="need_help", facility="TestFab").inc(2)


def test_active_events_set_with_labels_does_not_raise():
    ACTIVE_EVENTS.labels(severity="high").set(5)
    ACTIVE_EVENTS.labels(severity="low").set(0)


def test_cache_operations_inc_with_labels_does_not_raise():
    CACHE_OPERATIONS.labels(op="hit").inc()
    CACHE_OPERATIONS.labels(op="miss").inc()


def test_generate_latest_exposes_metric_names():
    # Trigger at least one observation so the names appear in the output.
    REPORTS_SUBMITTED.labels(status="safe", facility="ExposeTest").inc()
    ACTIVE_EVENTS.labels(severity="critical").set(1)
    CACHE_OPERATIONS.labels(op="hit").inc()

    output = generate_latest().decode("utf-8")
    assert "safety_reports_submitted_total" in output
    assert "safety_active_events_count" in output
    assert "safety_cache_operations_total" in output
