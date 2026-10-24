"""Download Jan 2026 wind actuals + forecasts from Elexon into backend/data/.

    cd backend
    python -m scripts.fetch_snapshot

Takes a minute or so. Commit the CSVs so deployed apps start instantly.
"""
import logging

from app import store
from app.config import DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

if __name__ == "__main__":
    actuals, forecasts = store.download()
    store.save(actuals, forecasts, DATA_DIR)
    print(f"actuals:   {len(actuals):>6} rows  {actuals.start_time.min()} -> {actuals.start_time.max()}")
    print(f"forecasts: {len(forecasts):>6} rows  {forecasts.publish_time.nunique()} publish runs")
    print(f"saved to {DATA_DIR}")
