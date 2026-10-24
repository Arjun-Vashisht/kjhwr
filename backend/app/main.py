import logging
import os
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import analysis
from .config import DEFAULT_GATE, FIRST_DECISION_DAY, GATE_CLOSURES, HORIZONS, LAST_DECISION_DAY
from .store import get_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Windcast API")

# Only needed for local dev where Vite runs on another port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)

FIRST_DELIVERY = FIRST_DECISION_DAY + timedelta(days=1)
LAST_DELIVERY = LAST_DECISION_DAY + timedelta(days=1)


def _check_gate(gate: str):
    if gate not in GATE_CLOSURES:
        raise HTTPException(400, f"gate must be one of {list(GATE_CLOSURES)}")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    actuals, forecasts = get_data()
    return {
        "first_delivery_day": FIRST_DELIVERY.isoformat(),
        "last_delivery_day": LAST_DELIVERY.isoformat(),
        "gates": [{"time": k, "label": v} for k, v in GATE_CLOSURES.items()],
        "default_gate": DEFAULT_GATE,
        "horizons": HORIZONS,
        "counts": {
            "actual_points": int(len(actuals)),
            "forecast_rows": int(len(forecasts)),
            "forecast_runs": int(forecasts.publish_time.nunique()),
        },
    }


@app.get("/api/decision")
def decision(day: date, gate: str = DEFAULT_GATE):
    _check_gate(gate)
    if not FIRST_DELIVERY <= day <= LAST_DELIVERY:
        raise HTTPException(400, f"day must be between {FIRST_DELIVERY} and {LAST_DELIVERY}")
    actuals, forecasts = get_data()
    return analysis.decision_day(actuals, forecasts, day, gate)


@app.get("/api/accuracy")
def accuracy(
    horizon: float | None = Query(None, ge=0, le=72),
    gate: str | None = None,
):
    """Month-wide accuracy, either at a fixed lead time or as-of an auction gate."""
    if (horizon is None) == (gate is None):
        raise HTTPException(400, "pass exactly one of horizon or gate")

    actuals, forecasts = get_data()
    if gate is not None:
        _check_gate(gate)
        picked = analysis.at_gate(forecasts, gate)
    else:
        picked = analysis.at_horizon(forecasts, horizon)

    df = analysis.compare(actuals, picked)
    daily = analysis.daily_energy(df).reset_index()
    daily["day"] = daily["day"].astype(str)

    return {
        "metrics": analysis.metrics(df),
        "series": [
            {"time": r.start_time.isoformat(), "actual": r.actual, "forecast": r.forecast}
            for r in df.itertuples()
        ],
        "histogram": analysis.histogram(df.error),
        "by_hour": analysis.by_hour(df),
        "daily": daily.round(1).to_dict(orient="records"),
    }


@app.get("/api/horizons")
def horizons():
    actuals, forecasts = get_data()
    return analysis.by_horizon(actuals, forecasts, HORIZONS)


# In the Docker image the built React app lives next to the API and we serve
# it from here, so the whole thing is one container / one URL.
static_dir = Path(os.getenv("STATIC_DIR", "/nonexistent"))
if static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = static_dir / path
        if path and file.is_file():
            return FileResponse(file)
        return FileResponse(static_dir / "index.html")
