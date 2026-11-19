# Data Dictionary: WeatherFlow hourly weather

- **Source:** Open-Meteo Forecast API, https://api.open-meteo.com/v1/forecast
- **Licence:** Open-Meteo data is CC BY 4.0
- **Refresh frequency:** Hourly values; fetched by running `extract.py` (manual for now)
- **Grain:** One row per city per hour

| Column | Type | Unit | Description | Example | Nullable? | Source |
|---|---|---|---|---|---|---|
| time | datetime | Europe/London local time | Start of the hourly period (arrives as text, converted with `pd.to_datetime`) | 2026-11-18T14:00 | No | Open-Meteo `hourly.time` |
| temperature_2m | float | °C | Air temperature 2 m above ground | 8.4 | Yes | Open-Meteo `hourly.temperature_2m` |
| relative_humidity_2m | int | % | Relative humidity 2 m above ground | 91 | Yes | Open-Meteo `hourly.relative_humidity_2m` |
| apparent_temperature | float | °C | Perceived temperature (wind chill and humidity) | 6.2 | Yes | Open-Meteo `hourly.apparent_temperature` |
| precipitation | float | mm | Rain, showers and snow in the preceding hour | 0.2 | Yes | Open-Meteo `hourly.precipitation` |
| wind_speed_10m | float | km/h | Wind speed 10 m above ground | 11.9 | Yes | Open-Meteo `hourly.wind_speed_10m` |
| weather_code | int | WMO code | Weather condition (0 clear, 3 overcast, 51-55 drizzle, 61-63 rain) | 3 | Yes | Open-Meteo `hourly.weather_code` |
| city | string | n/a | City name added by `flatten()` | London | No | Added by our script |
| latitude | float | degrees | Grid point latitude returned by the API (may differ slightly from the requested one) | 51.51147 | No | Open-Meteo response `latitude` |
| longitude | float | degrees | Grid point longitude returned by the API | -0.13078 | No | Open-Meteo response `longitude` |