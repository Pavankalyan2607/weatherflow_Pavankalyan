-- Q1: Data coverage. How many hourly rows do we hold per city, and what
-- time range do they cover? Business question: do we have complete data?
SELECT city,
       COUNT(*)         AS row_count,
       MIN(observed_at) AS first_observed_at,
       MAX(observed_at) AS last_observed_at
FROM weather_hourly
GROUP BY city
ORDER BY city;

-- Q2: Average temperature per city for yesterday.
-- Business question: which city was warmest yesterday?
SELECT city,
       ROUND(AVG(temperature_c), 1) AS avg_temperature_c
FROM weather_hourly
WHERE date(observed_at) = date('now', '-1 day')
GROUP BY city
ORDER BY avg_temperature_c DESC;

-- Q3: The 5 windiest hours across all cities.
-- Business question: when and where were the strongest winds?
SELECT city,
       observed_at,
       wind_speed_kmh
FROM weather_hourly
ORDER BY wind_speed_kmh DESC
LIMIT 5;