from datetime import date

import numpy as np
import pandas as pd
import pytest

from app import analysis
from app.timeutil import delivery_day_of, delivery_window, gate_closure


def ts(s):
    return pd.Timestamp(s, tz="UTC")


@pytest.fixture
def fake():
    """Three weeks of fake data. Forecasts come out every 3h and cover 48h hourly.
    Forecast error grows with lead time so horizon tests have something to see."""
    rng = np.random.default_rng(0)
    half_hours = pd.date_range("2025-12-30", "2026-01-20", freq="30min", tz="UTC")
    truth = 8000 + 4000 * np.sin(np.arange(len(half_hours)) / 40)
    actuals = pd.DataFrame({"start_time": half_hours, "generation": truth})
    lookup = actuals.set_index("start_time").generation

    rows = []
    for pub in pd.date_range("2025-12-29", "2026-01-20", freq="3h", tz="UTC"):
        for t in pd.date_range(pub + pd.Timedelta(hours=1), periods=48, freq="1h"):
            if t in lookup.index:
                lead = (t - pub).total_seconds() / 3600
                rows.append((t, pub, lookup[t] + rng.normal(0, 20 * lead)))
    forecasts = pd.DataFrame(rows, columns=["start_time", "publish_time", "generation"])
    return actuals, forecasts


def test_delivery_window_january_is_gmt():
    start, end = delivery_window(date(2026, 1, 2))
    assert start == ts("2026-01-01 23:00")
    assert end == ts("2026-01-02 23:00")


def test_delivery_window_handles_summer_time():
    start, _ = delivery_window(date(2026, 7, 2))
    assert start == ts("2026-07-01 22:00")  # 23:00 BST


def test_gate_is_day_before():
    assert gate_closure(date(2026, 1, 15), "09:20") == ts("2026-01-14 09:20")


def test_23_00_belongs_to_next_delivery_day():
    s = pd.Series([ts("2026-01-05 22:30"), ts("2026-01-05 23:00")])
    assert list(delivery_day_of(s)) == [date(2026, 1, 5), date(2026, 1, 6)]


def test_horizon_never_peeks_into_the_future(fake):
    _, forecasts = fake
    for h in (0, 4, 24):
        picked = analysis.at_horizon(forecasts, h)
        lead = (picked.start_time - picked.publish_time).dt.total_seconds() / 3600
        assert (lead >= h).all()


def test_horizon_takes_the_latest_allowed_run(fake):
    _, forecasts = fake
    picked = analysis.at_horizon(forecasts, 4).set_index("start_time")
    t = ts("2026-01-10 12:00")
    # runs are at 00,03,06,09..., cutoff is 08:00, so the 06:00 run should win
    assert picked.loc[t, "publish_time"] == ts("2026-01-10 06:00")


def test_gate_uses_only_what_was_known_at_gate(fake):
    _, forecasts = fake
    picked = analysis.at_gate(forecasts, "09:20")
    days = delivery_day_of(picked.start_time)
    gates = days.map(lambda d: gate_closure(d, "09:20"))
    assert (picked.publish_time <= gates).all()
    # 09:00 run is the last one before 09:20
    assert (picked.publish_time.dt.strftime("%H:%M") == "09:00").all()


def test_error_sign_is_forecast_minus_actual():
    actuals = pd.DataFrame({"start_time": [ts("2026-01-05")], "generation": [100.0]})
    picked = pd.DataFrame({
        "start_time": [ts("2026-01-05")],
        "publish_time": [ts("2026-01-04")],
        "forecast": [130.0],
    })
    df = analysis.compare(actuals, picked)
    assert df.error.iloc[0] == 30
    assert df.lead_hours.iloc[0] == 24


def test_error_grows_with_horizon(fake):
    actuals, forecasts = fake
    rows = analysis.by_horizon(actuals, forecasts, [1, 12, 36])
    maes = [r["mae"] for r in rows]
    assert maes[0] < maes[1] < maes[2]


def test_metrics_on_empty_frame():
    assert analysis.metrics(pd.DataFrame(columns=["error", "actual", "lead_hours"])) == {"n": 0}


def test_decision_day_band_and_energy(fake):
    actuals, forecasts = fake
    out = analysis.decision_day(actuals, forecasts, date(2026, 1, 10), "09:20")

    assert out["gate_utc"].startswith("2026-01-09T09:20")
    assert out["forecast_published"].startswith("2026-01-09T09:00")
    with_fc = [p for p in out["series"] if p["forecast"] is not None]
    assert len(with_fc) == 24  # hourly forecast over a 24h delivery day
    assert len(out["series"]) == 48  # actuals every half hour
    for p in with_fc:
        assert p["low"] <= p["high"]
    lo, hi = out["energy"]["range_mwh"]
    assert lo <= hi
