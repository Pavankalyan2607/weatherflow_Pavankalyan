# ERD: WeatherFlow star schema

## Grain

One row per city, per hour, per source.

## Diagram

```mermaid
erDiagram
    dim_city ||--o{ fact_weather_hourly : "city_id"
    dim_date ||--o{ fact_weather_hourly : "date_id"

    dim_city {
        INTEGER city_id PK
        TEXT city_name
        TEXT country
        REAL latitude
        REAL longitude
    }

    dim_date {
        INTEGER date_id PK
        TEXT full_date
        INTEGER year
        INTEGER quarter
        INTEGER month
        TEXT month_name
        INTEGER day
        TEXT day_of_week
        INTEGER day_of_week_num
        INTEGER is_weekend
    }

    fact_weather_hourly {
        INTEGER city_id PK
        TEXT observed_at_utc PK
        TEXT source PK
        INTEGER date_id FK
        INTEGER hour_local
        REAL temperature_c
        REAL feels_like_c
        REAL humidity_pct
        REAL precipitation_mm
        REAL wind_speed_kmh
        INTEGER beaufort_scale
        INTEGER weather_code
        TEXT weather_category
        INTEGER is_daylight
        TEXT outdoor_work_risk
        TEXT ingested_at_utc
    }
```

## Design notes

- **Primary key** of the fact table is (city_id, observed_at_utc, source). `source` is in the key because a second weather source will be added next week.
- **date_id** is the London (local) date from `observed_at_local`, because the business plans by UK calendar day. A reading at 23:30 UTC on 30 June belongs to 1 July in London.
- **city_id** is a surrogate key assigned in `dim_city` during the load. Upserts keep it stable.
- **Idempotent load:** facts use `INSERT ... ON CONFLICT DO UPDATE`, and the whole load runs in one transaction, so a failure leaves no partial rows.