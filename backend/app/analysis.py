"""Forecast selection and error stats. Pure pandas, no I/O, so it's easy to test.

Sign convention everywhere: error = forecast - actual.
Positive error = forecast was too high = less wind turned up than planned, so
the desk would have under-bought and ended up short.
"""
from datetime import date

import numpy as np
import pandas as pd

from .timeutil import delivery_day_of, delivery_window, gate_closure


# ---------- picking which forecast counts ----------

def latest_before(forecasts: pd.DataFrame, cutoff: pd.Series) -> pd.DataFrame:
    """For each target time, the most recent forecast published at or before its cutoff.

    `cutoff` is indexed by start_time. Targets with no qualifying forecast are dropped.
    """
    f = forecasts.merge(cutoff.rename("cutoff"), left_on="start_time", right_index=True)
    f = f[f.publish_time <= f.cutoff]
    f = f.sort_values("publish_time").groupby("start_time", as_index=False).last()
    return f[["start_time", "publish_time", "generation"]].rename(columns={"generation": "forecast"})


def at_horizon(forecasts: pd.DataFrame, hours: float) -> pd.DataFrame:
    """Latest forecast issued at least `hours` before each target time."""
    targets = pd.DatetimeIndex(forecasts.start_time.drop_duplicates())
    cutoff = pd.Series(targets - pd.Timedelta(hours=hours), index=targets)
    return latest_before(forecasts, cutoff)


def at_gate(forecasts: pd.DataFrame, gate: str) -> pd.DataFrame:
    """Latest forecast available when the auction for that target's delivery day closed."""
    targets = forecasts.start_time.drop_duplicates()
    days = delivery_day_of(targets)
    gates = {d: gate_closure(d, gate) for d in days.unique()}
    cutoff = pd.Series([gates[d] for d in days], index=pd.DatetimeIndex(targets))
    return latest_before(forecasts, cutoff)


def compare(actuals: pd.DataFrame, picked: pd.DataFrame) -> pd.DataFrame:
    """Join picked forecasts to actuals. Only rows that have both are kept."""
    df = picked.merge(
        actuals.rename(columns={"generation": "actual"}), on="start_time", how="inner"
    )
    df["error"] = df.forecast - df.actual
    df["lead_hours"] = (df.start_time - df.publish_time).dt.total_seconds() / 3600
    return df.sort_values("start_time").reset_index(drop=True)


# ---------- stats ----------

def _step_hours(times: pd.Series) -> float:
    """Spacing between points in hours (0.5 for half-hourly, 1 for hourly)."""
    if len(times) < 2:
        return 0.5
    return float(times.sort_values().diff().dropna().median().total_seconds() / 3600)


def metrics(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n": 0}
    err = df.error
    mean_actual = float(df.actual.mean())
    mae = float(err.abs().mean())
    return {
        "n": int(len(df)),
        "mae": mae,
        "rmse": float(np.sqrt((err ** 2).mean())),
        "bias": float(err.mean()),
        # MAE relative to average output. MAPE is useless for wind because
        # actuals get close to zero on calm days.
        "nmae": mae / mean_actual if mean_actual else None,
        "p10": float(err.quantile(0.10)),
        "p50": float(err.quantile(0.50)),
        "p90": float(err.quantile(0.90)),
        "p95_abs": float(err.abs().quantile(0.95)),
        "max_abs": float(err.abs().max()),
        "mean_actual": mean_actual,
        "mean_lead_hours": float(df.lead_hours.mean()),
    }


def histogram(errors: pd.Series, width: int = 500) -> list:
    if errors.empty:
        return []
    lo = int(np.floor(errors.min() / width) * width)
    hi = int(np.ceil(errors.max() / width) * width) + width
    counts, edges = np.histogram(errors, bins=range(lo, hi + 1, width))
    return [{"from": int(a), "to": int(a + width), "count": int(c)} for a, c in zip(edges[:-1], counts)]


def by_hour(df: pd.DataFrame) -> list:
    """MAE and bias by UK hour of day. Wind errors aren't flat through the day."""
    if df.empty:
        return []
    hour = df.start_time.dt.tz_convert("Europe/London").dt.hour
    g = df.assign(hour=hour, abs_err=df.error.abs()).groupby("hour")
    out = g.agg(mae=("abs_err", "mean"), bias=("error", "mean"), n=("error", "size")).reset_index()
    return out.to_dict(orient="records")


def by_horizon(actuals, forecasts, horizons) -> list:
    rows = []
    for h in horizons:
        m = metrics(compare(actuals, at_horizon(forecasts, h)))
        rows.append({"horizon": h, **{k: m.get(k) for k in ("n", "mae", "rmse", "bias", "p10", "p90")}})
    return rows


def daily_energy(df: pd.DataFrame) -> pd.DataFrame:
    """MWh per delivery day, forecast vs actual, over matched points only."""
    step = _step_hours(df.start_time)
    d = df.assign(day=delivery_day_of(df.start_time))
    out = d.groupby("day").agg(
        forecast_mwh=("forecast", lambda s: s.sum() * step),
        actual_mwh=("actual", lambda s: s.sum() * step),
        points=("forecast", "size"),
    )
    out["error_mwh"] = out.forecast_mwh - out.actual_mwh
    return out


# ---------- the decision view ----------

def decision_day(actuals, forecasts, day: date, gate: str) -> dict:
    """Everything the desk would have seen for one delivery day, plus what actually happened.

    The uncertainty band comes from how wrong the gate-time forecast was on the
    *other* days of the month (leave-one-out), so a day never grades itself.
    """
    picked = at_gate(forecasts, gate)
    all_days = compare(actuals, picked)
    all_days["day"] = delivery_day_of(all_days.start_time)

    others = all_days[all_days.day != day]
    q10, q90 = (others.error.quantile([0.1, 0.9]).tolist() if len(others) else (0.0, 0.0))

    start, end = delivery_window(day)
    act = actuals[(actuals.start_time >= start) & (actuals.start_time < end)]
    fc = picked[(picked.start_time >= start) & (picked.start_time < end)]

    # outer join so the chart shows actuals every half hour even if WINDFOR is hourly
    series = act.rename(columns={"generation": "actual"}).merge(fc, on="start_time", how="outer")
    series = series.sort_values("start_time")
    # actual = forecast - error, so the 10th pct error gives the high side
    series["low"] = (series.forecast - q90).clip(lower=0)
    series["high"] = (series.forecast - q10).clip(lower=0)

    today = all_days[all_days.day == day]

    energy = daily_energy(all_days)
    other_energy = energy[energy.index != day].error_mwh
    e10, e90 = (other_energy.quantile([0.1, 0.9]).tolist() if len(other_energy) else (0.0, 0.0))
    this_energy = energy.loc[day] if day in energy.index else None

    return {
        "day": day.isoformat(),
        "gate": gate,
        "gate_utc": gate_closure(day, gate).isoformat(),
        "window": [start.isoformat(), end.isoformat()],
        "forecast_published": fc.publish_time.max().isoformat() if not fc.empty else None,
        "series": [
            {
                "time": r.start_time.isoformat(),
                "actual": _num(r.actual),
                "forecast": _num(r.forecast),
                "low": _num(r.low),
                "high": _num(r.high),
            }
            for r in series.itertuples()
        ],
        "band": {"q10_error": q10, "q90_error": q90, "other_days": int(others.day.nunique())},
        "energy": None if this_energy is None else {
            "forecast_mwh": float(this_energy.forecast_mwh),
            "actual_mwh": float(this_energy.actual_mwh),
            # plausible range for the day's total, from the other days' daily misses
            "range_mwh": [
                max(0.0, float(this_energy.forecast_mwh - e90)),
                max(0.0, float(this_energy.forecast_mwh - e10)),
            ],
        },
        "metrics": metrics(today),
    }


def _num(x):
    return None if pd.isna(x) else round(float(x), 1)
