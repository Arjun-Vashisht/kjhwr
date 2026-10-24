"""Thin client for the two Elexon BMRS stream endpoints we need.

Both endpoints are public, no API key. The /stream variants return a plain
JSON list, which is a lot quicker than the paginated ones.
"""
import logging
import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from .config import ELEXON_BASE

log = logging.getLogger(__name__)

# WINDFOR is chunked by publish time. A week of forecasts is small enough
# that Elexon never times out on it.
CHUNK = timedelta(days=7)


def _get(path, params, retries=3):
    url = f"{ELEXON_BASE}{path}"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            body = resp.json()
            # stream endpoints give a list, the normal ones wrap it in {"data": [...]}
            return body["data"] if isinstance(body, dict) else body
        except (requests.RequestException, ValueError) as exc:
            if attempt == retries:
                raise
            log.warning("elexon %s failed (%s), retry %d", path, exc, attempt)
            time.sleep(2 * attempt)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_actuals(first_day: date, last_day: date) -> pd.DataFrame:
    """Half-hourly wind outturn (FUELHH, fuelType=WIND) for settlement dates in range."""
    rows = _get(
        "/datasets/FUELHH/stream",
        {
            "settlementDateFrom": first_day.isoformat(),
            "settlementDateTo": last_day.isoformat(),
            "fuelType": "WIND",
        },
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["start_time", "generation"])

    df = df[df["fuelType"] == "WIND"]  # in case the filter is ever ignored
    df = df.rename(columns={"startTime": "start_time"})
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
    # the same half hour can be republished; keep the most recent version
    if "publishTime" in df:
        df = df.sort_values("publishTime")
    df = df.drop_duplicates("start_time", keep="last")
    return df[["start_time", "generation"]].sort_values("start_time").reset_index(drop=True)


def fetch_forecasts(publish_from: datetime, publish_to: datetime) -> pd.DataFrame:
    """Every WINDFOR forecast published in [publish_from, publish_to)."""
    frames = []
    cursor = publish_from
    while cursor < publish_to:
        end = min(cursor + CHUNK, publish_to)
        log.info("WINDFOR %s -> %s", cursor, end)
        rows = _get(
            "/datasets/WINDFOR/stream",
            {"publishDateTimeFrom": _iso(cursor), "publishDateTimeTo": _iso(end)},
        )
        if rows:
            frames.append(pd.DataFrame(rows))
        cursor = end

    if not frames:
        return pd.DataFrame(columns=["start_time", "publish_time", "generation"])

    df = pd.concat(frames, ignore_index=True)
    df = df.rename(columns={"startTime": "start_time", "publishTime": "publish_time"})
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
    df["publish_time"] = pd.to_datetime(df["publish_time"], utc=True)
    # chunk edges can overlap by one publish run
    df = df.drop_duplicates(["start_time", "publish_time"])
    return df[["start_time", "publish_time", "generation"]].sort_values(
        ["publish_time", "start_time"]
    ).reset_index(drop=True)
