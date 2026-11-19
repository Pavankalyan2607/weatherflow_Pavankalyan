-- Q1: Data coverage. Rows per city and the time range they cover.
SELECT c.city_name,
       COUNT(*)                 AS row_count,
       MIN(f.observed_at_utc)   AS first_observed_at_utc,
       MAX(f.observed_at_utc)   AS last_observed_at_utc
FROM fact_weather_hourly AS f
JOIN dim_city AS c ON c.city_id = f.city_id
GROUP BY c.city_name
ORDER BY c.city_name;

-- Q2: Average temperature per city per London calendar day. Which city is warmest?
SELECT c.city_name,
       d.full_date,
       ROUND(AVG(f.temperature_c), 1) AS avg_temperature_c
FROM fact_weather_hourly AS f
JOIN dim_city AS c ON c.city_id = f.city_id
JOIN dim_date AS d ON d.date_id = f.date_id
GROUP BY c.city_name, d.full_date
ORDER BY d.full_date, avg_temperature_c DESC;

-- Q3: The 5 windiest hours across all cities.
SELECT c.city_name,
       f.observed_at_utc,
       f.wind_speed_kmh,
       f.beaufort_scale
FROM fact_weather_hourly AS f
JOIN dim_city AS c ON c.city_id = f.city_id
ORDER BY f.wind_speed_kmh DESC
LIMIT 5;

-- Q4: Average wind by city on weekends vs weekdays.
SELECT c.city_name,
       CASE WHEN d.is_weekend = 1 THEN 'weekend' ELSE 'weekday' END AS day_type,
       ROUND(AVG(f.wind_speed_kmh), 1) AS avg_wind_kmh,
       COUNT(*) AS hours
FROM fact_weather_hourly AS f
JOIN dim_city AS c ON c.city_id = f.city_id
JOIN dim_date AS d ON d.date_id = f.date_id
GROUP BY c.city_name, d.is_weekend
ORDER BY c.city_name, day_type;

-- Q5: Share of hours with high outdoor work risk, per city.
SELECT c.city_name,
       SUM(f.outdoor_work_risk = 'high') AS high_risk_hours,
       COUNT(*) AS total_hours,
       ROUND(100.0 * SUM(f.outdoor_work_risk = 'high') / COUNT(*), 1) AS pct_high_risk
FROM fact_weather_hourly AS f
JOIN dim_city AS c ON c.city_id = f.city_id
GROUP BY c.city_name
ORDER BY pct_high_risk DESC;