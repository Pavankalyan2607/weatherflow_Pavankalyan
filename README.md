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
