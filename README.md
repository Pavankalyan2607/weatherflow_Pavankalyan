# weatherflow_Pavankalyan

**Author:** Pavankalyan Adepu

## Goal
WeatherFlow is a data engineering project that builds a repeatable pipeline to collect weather data from a public API, clean and transform it with Python and pandas, and store it in a database so it can be queried with SQL. The aim is to turn raw, messy weather data into reliable, analysis-ready datasets.

## Project structure
- `data/` – raw and processed data (ignored by Git)
- `docs/` – documentation
- `notebooks/` – Jupyter notebooks for exploration
- `sql/` – SQL scripts

## How to set up

1. Clone the repo:
   ```
   git clone https://github.com/Pavankalyan2607/weatherflow_Pavankalyan.git
   cd weatherflow_Pavankalyan
   ```
2. Create a virtual environment (Python 3.11+):
   ```
   python -m venv .venv
   ```
3. Activate it:
   - Windows: `.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`
4. Install dependencies:
   ```
   pip install -r requirements.txt
   pip install -e .
   ```
   ## How to run the pipeline

Make sure the virtual environment is active (`(.venv)` shows in the terminal prompt), then run:

    python -m weatherflow run

This runs Extract, Transform and Load in one command. It calls Open-Meteo for 5 UK cities, saves the raw JSON under `data/raw/<date>/`, cleans the data and loads it into `weather.db` (table `weather_hourly`). Re-running is safe: rows are replaced by `(city, observed_at)`, so there are no duplicates.

Example output:

    Loaded 240 rows

Example queries are in `sql/week1_queries.sql`.


## Running the tests

Install dev dependencies and the package in editable mode, then run:

    pip install -e .
    pip install pytest pytest-cov
    pytest -v --cov=src --cov-report=term-missing

No test calls the real API: HTTP requests are mocked and a trimmed Open-Meteo
response is stored in `tests/fixtures/open_meteo_london.json`.

Latest result: 64 passed.

    Name                           Stmts   Miss  Cover
    ----------------------------------------------------
    TOTAL                            444     44    90%

    ## Backfill and incremental loads

    python -m weatherflow run                       # incremental: only what is new, plus the forecast
    python -m weatherflow backfill --days 30        # 30 days ending 5 days ago
    python -m weatherflow backfill --start-date 2026-10-01 --end-date 2026-10-31

- `run` reads a high-water mark per city: the latest loaded hour that has already
  happened (`observed_at_utc <= now`, source `open_meteo_forecast`). It requests from
  2 hours before the mark to the end of today, so forecast hours are refreshed on
  every run. With no data yet it falls back to `past_days=1`.
- `backfill` uses the archive API, which lags real time by about 5 days, so the
  default end date is today minus 5 days. It fetches 7-day chunks per city with a
  1 second pause, source `open_meteo_archive`.
- Both commands use the same transform, validate and load code. Loads are upserts,
  so re-running either command does not change row counts.

## Source layout

- `extract.py`: API calls, retries, raw JSON landing, date chunks
- `transform.py`: cleaning, derived metrics
- `validate.py`: data quality checks and quarantine
- `load.py`: star schema upserts (SQLite) and Parquet
- `watermark.py`: high-water mark and incremental window logic
- `pipeline.py`: `run` and `backfill`
- `__main__.py`: command line