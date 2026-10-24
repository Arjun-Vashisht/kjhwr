"""GB market time conventions.

A day-ahead "delivery day" D runs 23:00 on D-1 to 23:00 on D, UK local time.
The auction for D closes on D-1 in the morning. All of this is local time, so
we convert carefully (January is GMT anyway, but it costs nothing to be right).
"""
from datetime import date, datetime, time, timedelta

import pandas as pd

from .config import UK_TZ


def _local(d: date, t: time) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(d, t)).tz_localize(UK_TZ)


def delivery_window(day: date):
    """UTC [start, end) of delivery day `day`."""
    start = _local(day - timedelta(days=1), time(23, 0))
    end = _local(day, time(23, 0))
    return start.tz_convert("UTC"), end.tz_convert("UTC")


def gate_closure(day: date, gate: str) -> pd.Timestamp:
    """UTC time the auction for delivery day `day` closes. gate is 'HH:MM' local."""
    hh, mm = (int(x) for x in gate.split(":"))
    return _local(day - timedelta(days=1), time(hh, mm)).tz_convert("UTC")


def delivery_day_of(ts: pd.Series) -> pd.Series:
    """Delivery day each UTC timestamp belongs to (23:00 local rolls into tomorrow)."""
    local = ts.dt.tz_convert(UK_TZ) + pd.Timedelta(hours=1)
    return local.dt.date
