# Week 2 Reflection

## What I built
- Turned the Week 1 script into a proper package: src layout, config.yaml, logging, retries with backoff
- Transform step with derived metrics (Fahrenheit, m/s, Beaufort scale, outdoor work risk) and Parquet output
- Star schema in SQLite (dim_city, dim_date, fact_weather_hourly) with idempotent upserts
- Data quality checks with a quarantine area and a report for every run
- A pytest suite (64 tests, 90% coverage on src/) with the API mocked
- A 30-day backfill (3,600 rows) and an incremental load that uses a high-water mark

## What was hard
- A small indentation mistake in config.yaml moved a section under the wrong key and the whole config stopped loading. I learned to check the config with a one-line Python command after every change.
- Several times I pasted code in the wrong place or with the wrong indentation (a terminal instead of the editor, a missing space in an import). Reading the exact line in the error message fixed each one quickly.
- The high-water mark was the trickiest idea. Each run also loads forecast hours, so the latest loaded hour can be in the future. The mark has to ignore hours that have not happened yet, otherwise the next run would skip the hours in between.

## What I learned
- Idempotency: I loaded the same data three times and the row count stayed at 240. The primary key plus an upsert makes re-runs safe. Backfill is safe in the same way (3,600 rows, then 0 new and 3,600 updated).
- Transactions: when I forced a CHECK constraint failure, nothing was written (0 rows), because the whole load runs in one transaction.
- Data quality checks and unit tests are different things. A data quality check looks at the data of this run (is there a 99 C row today?). A unit test checks my code with fixed input.
- Mocking the API makes tests fast and free, and it lets me test failures like a 503 or a timeout that I could not trigger on purpose with the real API.
- 100% coverage is not the goal. I wrote tests for the rules and the boundaries (exactly 4 mm of rain, Beaufort 7, 0 C), and the coverage followed.

## Check your understanding
- When should a check fail the whole run? When the problem is with the dataset as a whole (duplicate keys, a missing city). A single bad row (99 C) is quarantined and the rest continues.
- Why a 2-hour overlap in the incremental window? Some recent hours are corrected a little later by the API. The overlap fetches them again and the upsert updates them without creating duplicates.
- How to reprocess history after changing a transformation rule? Keep the raw JSON unchanged in the raw zone and run transform, validate and load over it again. The upsert replaces the old rows.

## What I would do differently
- Write the tests earlier, together with each task, instead of at the end.
- Add the code review step earlier in the week so there is time to respond to comments.
## Code review
My Task 2.6 PR is open and I have requested a review from my partner. I have not received comments yet, so I have not been able to respond to them. I will reply to every comment and merge once the review is done.