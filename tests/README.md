# Tests

Unit tests for the ETL, Spark and API code, run with [pytest](https://docs.pytest.org/). They
do not need Dask or Kaggle. The API query tests need a MongoDB (`MONGO_URI`) and are skipped
without one.

```bash
uv run pytest
```

Jenkins runs the same command (after `uv sync --locked` and `uv run ruff check .`) on every pull
request into `main` and on every change that reaches `main`, so any test added here is run there
too.

## Adding a test

1. Add a function whose name starts with `test_` to a file in this directory whose name starts
   with `test_` (an existing one, or a new `test_<module>.py`):

   ```python
   import pandas as pd

   from us_wildfires_big_data.etl.transform import hhmm_to_hour


   def test_hhmm_to_hour_reads_morning_times():
       assert hhmm_to_hour(pd.Series(["0930"])).tolist() == [9]
   ```

2. If it needs a new library, add it with `uv add --dev <package>` so `uv.lock` is updated;
   otherwise it fails in Jenkins with `ModuleNotFoundError`.
3. Check it is found and passes: `uv run pytest --collect-only -q`, then `uv run pytest`.
4. Push and open a pull request into `main`.
