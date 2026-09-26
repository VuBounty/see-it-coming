from datetime import datetime, timezone
from app.presentation import health_status, market_state, forecast_ui_state, scientific_metrics

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def test_health_states():
    assert health_status("2026-09-26T11:30:00+00:00", 6, 6, NOW) == "LIVE"
    assert health_status("2026-09-26T11:30:00+00:00", 4, 6, NOW) == "DEGRADED"
    assert health_status("2026-09-26T11:30:00+00:00", 0, 6, NOW) == "NO DATA"
    assert health_status("2026-09-26T09:00:00+00:00", 6, 6, NOW) == "STALE"


def test_market_state_is_data_driven():
    assert market_state(.10) == "QUIET"
    assert market_state(.30) == "WATCHING"
    assert market_state(.55) == "ELEVATED"
    assert market_state(.85) == "HIGH ANOMALY"
    assert market_state(.10, True) == "LOCKED FORECAST"


def test_forecast_freshness():
    assert forecast_ui_state("2026-09-26T11:50:00+00:00", None, NOW) == "FRESH_LOCK"
    assert forecast_ui_state("2026-09-26T11:30:00+00:00", None, NOW) == "NEWLY_LOCKED"
    assert forecast_ui_state("2026-09-26T10:00:00+00:00", None, NOW) == "LOCKED"
    assert forecast_ui_state("2026-09-26T11:59:00+00:00", "CORRECT", NOW) == "RESOLVED"


def test_scientific_metrics():
    p = [
        {"id": "1", "probability": .7},
        {"id": "2", "probability": .8},
        {"id": "3", "probability": .6},
    ]
    r = [
        {"prediction_id": "1", "outcome": "CORRECT"},
        {"prediction_id": "2", "outcome": "WRONG"},
    ]
    m = scientific_metrics(p, r)
    assert m["locked"] == 3
    assert m["resolved"] == 2
    assert m["correct"] == 1
    assert m["accuracy"] == .5
    assert round(m["brier"], 3) == .365
