# Reference Architecture: WeatherFlow-DataEngineering

Data flow from weather APIs to the dashboard. **E** = Extract, **T** = Transform, **L** = Load.
Built from README.md and IMPLEMENTATION.md; some edges are inferred from the docs.

```mermaid
flowchart LR
  A1["WeatherAPI"] --> F["Python fetcher<br/>scripts/weather_api.py<br/>E: Extract"]
  A2["OpenWeatherMap"] --> F
  F -. "raw backup" .-> R[("data/raw")]
  F --> P["Kafka producer<br/>E: Extract (transport)"]
  P --> T1[("Kafka topic<br/>weather-raw-data")]
  T1 --> S["Spark processor<br/>T: Transform<br/>clean, heat index, severity"]
  S --> T2[("Kafka topic<br/>weather-processed-data")]
  S --> D[("data/processed<br/>L: Load")]
  D --> G["generate_reports.py<br/>CSV / HTML / PNG"]
  G --> RP[("data/reports<br/>L: Load")]
  D --> UI["Flask dashboard<br/>port 8051<br/>Serving"]
  AF["Airflow DAG<br/>schedules and retries"] -.-> F
  AF -.-> S
  AF -.-> G
```

| Stage | Label |
|---|---|
| Fetch from APIs, publish to Kafka | E |
| Spark cleaning and derived metrics | T |
| Write to data/processed and data/reports | L |
| Dashboard reads stored data | Serving (after L) |
