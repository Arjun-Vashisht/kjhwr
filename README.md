# Windcast

A small web app for a day-ahead power desk. It shows the GB national wind forecast the desk
would actually have had in hand when the auction closed, and how wrong that forecast tends to be,
so wind can be netted off demand with a sensible error margin.

Scope is January 2026 purchase decisions (delivery days 2 Jan to 1 Feb), using only Elexon's
FUELHH (actual wind) and WINDFOR (wind forecast) datasets.

- **Live app:** _add your Heroku / Vercel URL here_
- **Video walkthrough:** _add your unlisted YouTube link here_

## What's in it

**Day-ahead view.** Pick a delivery day and an auction. The app finds the latest WINDFOR forecast
published before that auction's gate closure on the day before, and shows it with a 10–90% likely
range. The range comes from how that same forecast missed on the other days of the month. You can
turn on the actual outturn to see how it played out.

**Forecast accuracy.** Error stats for the whole month, either "as seen at the auction" or at a
fixed lead time (0–48 h). Includes MAE, RMSE, bias, error percentiles, how error grows with lead
time, error by hour of day, and daily energy forecast vs actual.

## Running it

### With Docker (easiest)

```bash
docker compose up --build
```

Open http://localhost:8000. The image builds the React app and serves it from the FastAPI server,
so it's one container and one port.

### Without Docker

Backend (Python 3.11+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Frontend (Node 20+), in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to the backend on port 8000.

### Data

On first request the backend pulls everything it needs from Elexon (no API key needed) and saves it
to `backend/data/` as CSV. January 2026 is in the past so it never changes. To fetch it up front:

```bash
cd backend
python -m scripts.fetch_snapshot
```

or inside Docker: `docker compose run --rm app python -m scripts.fetch_snapshot`

Commit the two CSVs so the deployed app starts instantly and doesn't depend on Elexon being up.

### Tests

```bash
cd backend
pytest
```

Tests use small generated data, no network. CI (`.github/workflows/ci.yml`) runs them plus a
frontend build on every push.

## How the forecast is chosen

This is the main logic, so worth spelling out.

- **Delivery day** D runs 23:00 on D-1 to 23:00 on D, UK time, same as the GB day-ahead auctions.
- **Gate closure** is on D-1: 09:20 for EPEX GB hourly, 09:50 for N2EX, 14:30 for the EPEX
  half-hourly auction. For each target half hour the app takes the newest forecast with
  `publishTime <= gate`. Nothing published after the gate is ever used.
- **Fixed lead time H** (accuracy page): for each target time T, newest forecast with
  `publishTime <= T - H`.
- **Error** is always `forecast - actual`. Positive means less wind came than forecast, so the
  desk would have bought too little.
- **Likely range** on the day view is leave-one-out: day D's band is built only from errors on the
  other days, so a day never grades itself.
- MAPE is left out on purpose. Wind output gets close to zero on calm days and percentage error
  blows up. The app uses MAE relative to average output instead.

## Files and folders

```
backend/
  app/
    main.py          FastAPI routes; also serves the built frontend in production
    analysis.py      forecast selection and error stats (pure pandas, no I/O)
    timeutil.py      delivery-day and gate-closure time handling (UK local time)
    store.py         loads the CSV snapshot, or fetches from Elexon if it's missing
    elexon.py        client for the FUELHH and WINDFOR stream endpoints
    config.py        dates, auction gates, horizons, paths
  scripts/
    fetch_snapshot.py  downloads Jan 2026 data into backend/data/
  tests/             pytest: time handling, no-lookahead checks, API behaviour
  data/              actuals.csv and forecasts.csv once fetched
  requirements.txt
  requirements-dev.txt
frontend/
  src/
    App.jsx          layout and tabs
    components/
      DecisionView.jsx  day-ahead view
      AccuracyView.jsx  accuracy page and its charts
    api.js           fetch wrapper
    format.js        number and UK date formatting
    styles.css
  vite.config.js
api/index.py         Vercel entry point (wraps the same FastAPI app)
Dockerfile           two-stage build: React, then Python
docker-compose.yml
heroku.yml           Heroku container deploy
vercel.json          Vercel deploy (alternative to Heroku)
requirements.txt     Python deps for Vercel only
```

## API

| Endpoint | What it returns |
| --- | --- |
| `GET /api/meta` | Date range, auction gates, horizons, row counts |
| `GET /api/decision?day=2026-01-15&gate=09:20` | Forecast at gate, likely range, actuals, day summary |
| `GET /api/accuracy?gate=09:20` or `?horizon=24` | Month metrics, series, histogram, by-hour, daily energy |
| `GET /api/horizons` | MAE / RMSE / bias / percentiles for each lead time |

Interactive docs at `/docs` when the server is running.

## Deploying

**Heroku** (container stack):

```bash
heroku create
heroku stack:set container
git push heroku main
```

**Vercel**: import the repo. `vercel.json` builds the frontend and runs the API from `api/index.py`
as a Python function. Make sure the CSV snapshot is committed, since the function can't write to
disk.

## Limitations and next steps

- FUELHH "WIND" is transmission-metered wind only, it doesn't include embedded (distribution
  connected) wind. WINDFOR is on the same basis so the comparison is fair, but total GB wind is
  higher than what's shown.
- WINDFOR is hourly, actuals are half-hourly. Errors are only computed where both exist.
- The likely range uses the rest of the month. In production it should use a rolling window of
  past days only, and probably be split by lead time and wind level, since errors are bigger in
  the middle of the power curve.
- Next would be adding demand and solar so the app shows the residual volume to buy, not just wind.

## Use of AI tools

I used Claude (Anthropic) to help write the code and this README. I've reviewed, run and tested
everything, and can walk through any part of it.
