import os
from datetime import date
from pathlib import Path

ELEXON_BASE = "https://data.elexon.co.uk/bmrs/api/v1"

UK_TZ = "Europe/London"

# Purchase decisions made in January 2026 -> delivery days 2 Jan .. 1 Feb.
FIRST_DECISION_DAY = date(2026, 1, 1)
LAST_DECISION_DAY = date(2026, 1, 31)

# GB day-ahead auction gate closures (UK local time). Delivery day for both
# runs 23:00 on D-1 to 23:00 on D.
GATE_CLOSURES = {
    "09:20": "EPEX GB day-ahead (hourly)",
    "09:50": "N2EX day-ahead (hourly)",
    "14:30": "EPEX GB half-hourly auction",
}
DEFAULT_GATE = "09:20"

# Horizons offered on the accuracy page, in hours.
HORIZONS = [0, 1, 2, 4, 6, 8, 12, 16, 20, 24, 30, 36, 42, 48]

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
ACTUALS_FILE = DATA_DIR / "actuals.csv"
FORECASTS_FILE = DATA_DIR / "forecasts.csv"
