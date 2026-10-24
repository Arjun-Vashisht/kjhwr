"""Loads actuals + forecasts once per process.

January 2026 is in the past, so the data doesn't change. We keep a CSV snapshot
in backend/data (made with scripts/fetch_snapshot.py) and only hit Elexon if
it's missing.
"""
import logging
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import elexon
from .config import (
    ACTUALS_FILE,
    FIRST_DECISION_DAY,
    FORECASTS_FILE,
    LAST_DECISION_DAY,
)
from .timeutil import delivery_window

log = logging.getLogger(__name__)


def target_range():
    """UTC [start, end) covering every delivery period we care about."""
    first_delivery = FIRST_DECISION_DAY + timedelta(days=1)
    last_delivery = LAST_DECISION_DAY + timedelta(days=1)
    return delivery_window(first_delivery)[0], delivery_window(last_delivery)[1]


def download():
    """Pull everything we need from Elexon. Returns (actuals, forecasts)."""
    start, end = target_range()

    actuals = elexon.fetch_actuals(FIRST_DECISION_DAY, LAST_DECISION_DAY + timedelta(days=1))

    # 3 days of slack before the first target so long horizons (48h) still
    # have something to pick from.
    publish_from = datetime.combine(FIRST_DECISION_DAY - timedelta(days=3), time(), timezone.utc)
    forecasts = elexon.fetch_forecasts(publish_from, end.to_pydatetime())

    return _trim(actuals, forecasts)


def _trim(actuals, forecasts):
    start, end = target_range()
    actuals = actuals[(actuals.start_time >= start) & (actuals.start_time < end)]
    forecasts = forecasts[(forecasts.start_time >= start) & (forecasts.start_time < end)]
    # a forecast published after its own target time isn't a forecast
    forecasts = forecasts[forecasts.publish_time <= forecasts.start_time]
    return actuals.reset_index(drop=True), forecasts.reset_index(drop=True)


def save(actuals, forecasts, folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    actuals.to_csv(folder / ACTUALS_FILE.name, index=False)
    forecasts.to_csv(folder / FORECASTS_FILE.name, index=False)


def _read_snapshot():
    actuals = pd.read_csv(ACTUALS_FILE, parse_dates=["start_time"])
    forecasts = pd.read_csv(FORECASTS_FILE, parse_dates=["start_time", "publish_time"])
    for df, cols in ((actuals, ["start_time"]), (forecasts, ["start_time", "publish_time"])):
        for c in cols:
            df[c] = pd.to_datetime(df[c], utc=True)
    return _trim(actuals, forecasts)


@lru_cache(maxsize=1)
def get_data():
    if ACTUALS_FILE.exists() and FORECASTS_FILE.exists():
        log.info("loading snapshot from %s", ACTUALS_FILE.parent)
        return _read_snapshot()

    log.info("no snapshot found, fetching from Elexon")
    actuals, forecasts = download()
    try:
        save(actuals, forecasts, ACTUALS_FILE.parent)
    except OSError:
        # read-only filesystem (serverless). Fine, we just keep it in memory.
        log.warning("could not write snapshot, keeping data in memory only")
    return actuals, forecasts
