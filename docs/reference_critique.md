# Reference Project Critique: WeatherFlow-DataEngineering

**Author:** Pavankalyan Adepu
**Reference:** https://github.com/SyedRoshanAli/WeatherFlow-DataEngineering
**Sources read:** README.md, IMPLEMENTATION.md and the `weather_flow/` folder tree

## What each tool does (one sentence each)

- **Kafka:** a message broker that holds events in topics so one program can publish data and others can read it later.
- **Spark:** a distributed engine that processes large datasets in parallel, in batch or streaming mode.
- **Airflow:** a scheduler that runs tasks in a defined order, retries failures and shows run history.
- **PostgreSQL:** a relational database that stores tables and answers SQL queries.
- **Docker:** packages each service with its dependencies so it runs the same on any machine.

## Component table

| Component | Tool used | What it does in this project | Batch or streaming? |
|---|---|---|---|
| Data source | WeatherAPI (primary), OpenWeatherMap (secondary), simulated station data | REST APIs return current weather per city. `scripts/weather_api.py` fetches them, standardises the format and saves a raw backup. | Batch (polled on a schedule) |
| Message broker | Kafka (with Zookeeper) | `producer.py` publishes readings to the topic `weather-raw-data`; `consumer.py` reads them. Decouples fetching from processing. | Streaming |
| Processing | Spark | `weather_processor.py` cleans data and derives metrics such as heat index and weather severity. | Docs claim both batch and streaming analytics |
| Orchestration | Airflow | `weather_pipeline_dag.py` schedules the pipeline, retries failures and shows run status in the UI (port 8091). | Batch (scheduled) |
| Storage | Local file data lake (`data/raw`, `data/processed`, `data/reports`); PostgreSQL only for Airflow metadata | Keeps raw files, processed output and generated reports. | Batch |
| Serving | Flask dashboard with ApexCharts (port 8051); `generate_reports.py` for CSV/HTML/PNG reports | Shows charts and lets users add cities. | Near real-time reads of stored data |
| Packaging | Docker Compose | Starts all services (Kafka, Spark, Airflow, Postgres, dashboard) on one `weather-network` with `docker-compose up -d`. | n/a |

## Critique

**What it does well.** Each job has its own tool and folder (ingestion, Kafka, Spark, Airflow, dashboard), so the pieces are easy to find and swap. Docker Compose starts the whole stack with one command, which makes setup repeatable. Kafdrop, the Spark UI and the Airflow UI give some visibility, and IMPLEMENTATION.md has a useful "Extending the Project" section.

**Problems and risks.**

1. **Secret in the docs.** README.md (Prerequisites, the `.env` example, the "Test Weather API" command, Data Sources) and IMPLEMENTATION.md all print the same WeatherAPI key (`1f5800c8...`). Once pushed, it lives in git history. The repo already contains `.env.template`, yet the docs print the real key instead of pointing to it. The key should be rotated and the docs should show a placeholder. The Airflow login `admin/admin` is also documented.

2. **Docs disagree with themselves and with the repo.** README says PostgreSQL is only the "Database for Airflow metadata", while IMPLEMENTATION.md says storage is "File-based storage with a data lake structure". README says the dashboard is Flask on port 8051, then tells readers to run `streamlit_dashboard.py` on port 8501. The README tree also does not match the real `weather_flow/` folder: `README.md` is listed inside it but sits at the repo root, and `docs/`, `.env.template`, `run_pipeline.py`, `run_standalone.sh`, `setup.py` and `streamlit_dashboard.py` exist but are missing from the tree.

3. **Weak testing and monitoring.** README's verification section is manual `docker exec` commands, and one creates a `weather_test` table inside Airflow's own metadata database. Loose scripts such as `test_weather_api.py` and `check_docker_logs.py` sit at the repo root. Nothing alerts anyone when a run fails; IMPLEMENTATION.md lists "proper monitoring and alerting" only as future work.

**Essential vs overkill (5 cities, hourly).** That is 5 x 24 = 120 records a day: tiny, and not a stream. Essential: a scheduled Python fetch with retries, one durable store (PostgreSQL or plain Parquet/CSV), secrets in `.env`, a simple dashboard, and Docker for repeatability. Airflow is borderline: useful for retries and run history, but cron would work. Overkill: Kafka (no multiple consumers, no replay need, hourly data does not need continuous transport) and Spark (pandas or SQL handles this on one laptop; Zookeeper and Spark workers add memory use and failure points).

## Check your understanding

**Explain Kafka to someone non-technical in one sentence.**
Kafka is like a post office sorting room: senders drop off messages, and receivers pick them up whenever they are ready, so neither has to wait for the other.

**Why might a team choose ELT instead of ETL with a cloud warehouse?**
Cloud warehouses have cheap storage and powerful compute, so it is simpler to load raw data first and transform it inside the warehouse with SQL. The raw data is kept, so transformations can be changed and re-run later without re-extracting from the source.
