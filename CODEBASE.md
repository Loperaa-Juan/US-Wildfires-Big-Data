# Codebase guide

This guide explains what the project does, how the repository is organized, and the order in
which to read the files to understand the whole codebase. It covers the **Dask ingestion stage**:
from the Kaggle download to the GeoJSON documents stored in MongoDB with a `2dsphere` index.

## 1. What the project does

The dataset is [1.88 Million US Wildfires](https://www.kaggle.com/datasets/rtatman/188-million-us-wildfires):
every wildfire reported in the United States between 1992 and 2015, with its location, date,
cause and size. The ingestion stage:

1. Downloads it automatically from Kaggle (no manual steps).
2. Extracts the useful columns from the SQLite database into a CSV.
3. Cleans it with Dask, in parallel partitions.
4. Converts each fire into a GeoJSON point and loads it into MongoDB in batches, with a
   `2dsphere` index so it can be queried by location (`$near`, `$geoWithin`, `$geoNear`).

## 2. Pipeline at a glance

```
Kaggle (1.88 Million US Wildfires)
   │  etl/download.py        kagglehub
   ▼
data/raw/FPA_FOD_20170508.sqlite          raw SQLite database, 1,880,465 fires
   │  etl/transform.py       pandas, chunks of 100,000 rows
   ▼
data/processed/fires.csv                  15 selected columns, readable dates
   │  etl/clean.py           Dask cluster + US Census county map
   ▼
data/processed/fires_clean.parquet        1,878,525 clean fires, 12 partitions
   │  etl/load_mongo.py      Dask cluster → GeoJSON → batches of 5,000
   ▼
MongoDB wildfires.fires                   1,878,525 GeoJSON Features, 2dsphere index
```

Each step reads the output of the previous one. Every step can be re-run safely: the download
skips files that already exist, the CSV and Parquet are overwritten, and the MongoDB load
updates documents instead of duplicating them.

## 3. Key concepts

Read this section first if any of these terms are new; the code relies on all of them.

### Dask: client, scheduler, workers and partitions

```
            your script (client)
     etl/clean.py, etl/load_mongo.py
                  │  sends the task graph
                  ▼
         ┌──────────────────┐
         │  Dask scheduler  │   decides which worker runs each task
         └────────┬─────────┘   dashboard: http://localhost:8787
        ┌─────────┴──────────┐
        ▼                    ▼
 dask-worker container  dask-worker container
 ┌──┬──┬──┬──┐          ┌──┬──┬──┬──┐
 │W1│W2│W3│W4│          │W5│W6│W7│W8│   one single-threaded worker per logical processor
 └──┴──┴──┴──┘          └──┴──┴──┴──┘
        │  each worker reads its partitions from data/ and writes to MongoDB
        ▼
   data/ (shared)  ·  MongoDB
```

- A **Dask DataFrame** is a large table split into **partitions**. Each partition is an ordinary
  pandas DataFrame, so the per-partition code (`clean_partition`, `load_partition`) is plain pandas.
- The **client** is the script you run. It doesn't process data itself: it builds a task graph
  ("read partition 3, clean it, write it") and sends it to the **scheduler**.
- The **scheduler** hands the tasks out to the **workers**, which do the actual work in parallel.
- `map_partitions(f)` applies `f` to every partition; `dask.delayed(f)(x)` turns a call into a
  task; nothing runs until `.compute()`, `dask.compute(...)` or `.to_parquet(...)` is called.
- Workers only help when there are at least as many partitions as workers, which is why both
  scripts make sure the data is split into enough partitions.

### GeoJSON and the `2dsphere` index

- Each fire is stored as a GeoJSON **Feature**: a `geometry` (a `Point`) plus `properties`
  (the other columns).
- GeoJSON coordinates are **`[longitude, latitude]`**, in that order. Swapping them is the most
  common mistake.
- A `2dsphere` index on `geometry` lets MongoDB answer distance and area queries on the
  sphere of the Earth. It also **validates** every point when it is inserted, which is why the
  index is created before loading.

### Idempotent load (upsert)

Each document's `_id` is the fire's `fod_id`, and documents are written with
`ReplaceOne(..., upsert=True)`: if the `_id` exists it is replaced, otherwise it is inserted.
Running the load twice leaves exactly 1,878,525 documents.

## 4. How to run it

The whole system starts with one command:

```bash
docker compose up --build
```

MongoDB, the Dask scheduler and the two worker containers start; then the `etl` service runs
`etl/pipeline.py` on that cluster (download → transform → clean → load) and exits. Kaggle
credentials come from a git-ignored `.env` file (`KAGGLE_USERNAME`, `KAGGLE_KEY`).

Locally, without Docker for the pipeline (Dask starts a local cluster with one worker per
logical processor):

```bash
uv sync
docker compose up -d mongo
uv run us-wildfires-big-data          # same pipeline
uv run python -m us_wildfires_big_data.etl.clean   # or a single step
```

Tests: `uv run pytest`. Lint and format: `uv run ruff check --fix` and `uv run ruff format`.

## 5. Repository structure

```
US-Wildfires-Big-Data/
├── README.md                      How to set up and run the project from scratch
├── CODEBASE.md                    This guide
├── pyproject.toml                 Project metadata and dependencies (managed with uv)
├── uv.lock                        Exact versions of every dependency
├── .python-version                Python version used by uv (3.13)
├── .env.example                   Every environment variable the code reads, with its default
├── .gitignore                     Keeps data, virtualenv, caches and .env out of git
├── docker/
│   ├── dask.Dockerfile            One image for the Dask scheduler, the workers and the ETL runner
│   └── spark.Dockerfile           Image for the Spark stage (src/us_wildfires_big_data/spark/)
├── .dockerignore                  Keeps data, venv, notebooks and secrets out of the image
├── docker-compose.yml             MongoDB, Dask scheduler, 2 Dask worker containers, ETL runner
├── data/                          Not in git (only the empty folders are)
│   ├── raw/                       FPA_FOD_20170508.sqlite, cb_2021_us_county_20m.zip
│   └── processed/                 fires.csv, fires_clean.parquet/
├── notebooks/
│   └── Exploratory_data_analysis.ipynb   EDA that tests and justifies each cleaning decision
├── src/us_wildfires_big_data/
│   ├── __init__.py                Empty package marker
│   ├── config.py                  Every setting and path; the only place that reads env vars
│   └── etl/
│       ├── download.py            Step 1: Kaggle → SQLite
│       ├── transform.py           Step 2: SQLite → CSV
│       ├── geojson.py             Pure functions: rows → GeoJSON Features
│       ├── cluster.py             Dask client: compose scheduler or local cluster
│       ├── clean.py               Step 3: CSV → clean Parquet (Dask)
│       ├── load_mongo.py          Step 4: Parquet → MongoDB (Dask)
│       └── pipeline.py            Runs steps 1–4 in order; what `docker compose up` runs
└── tests/
    ├── test_transform.py          Date and hour conversion
    ├── test_geojson.py            GeoJSON conversion and coordinate validation
    └── test_clean.py              Cleaning steps on a small fake county map
```

## 6. Reading order

Each file only depends on the ones before it, so reading in this order you never meet a name
you haven't seen yet.

### 6.1 `README.md`

How the project is installed (`uv sync`) and the command for each step.

### 6.2 `pyproject.toml` and `.env.example`

`pyproject.toml` lists the libraries the code uses:

| Library | Used for |
|---|---|
| `kagglehub` | Downloading the dataset |
| `pandas` | Reading the SQLite database and processing each partition |
| `dask[dataframe,distributed]` | Partitioned DataFrames, scheduler and workers |
| `geopandas` | Spatial join between fires and county polygons |
| `pymongo` | Writing to MongoDB |
| `pytest`, `ruff` (dev) | Tests, linting and formatting |

`.env.example` lists every setting that can be changed without touching the code.

### 6.3 `src/us_wildfires_big_data/config.py`

Every other module imports its settings from here. It is the only file that calls `os.getenv`;
each value falls back to a default, so nothing has to be configured to run locally.

| Group | Settings |
|---|---|
| Paths | `ROOT`, `DATA_DIR`, `RAW_DATA`, `PROCESSED_DATA`, `SQLITE_PATH`, `FIRES_CSV`, `FIRES_CLEAN`, `COUNTIES_ZIP` |
| Sources | `KAGGLE_DATASET`, `COUNTIES_URL` |
| MongoDB | `MONGO_URI`, `MONGO_DB`, `MONGO_COLLECTION`, `MONGO_BATCH_SIZE` |
| Dask | `DASK_SCHEDULER` (address of a running scheduler, set by Docker Compose), `DASK_WORKERS` (local cluster size, defaults to `os.cpu_count()`) |

Values come from the shell environment. A `.env` file is not loaded automatically; use
`uv run --env-file .env ...` if you want it.

### 6.4 `src/us_wildfires_big_data/etl/download.py`

Downloads the dataset with `kagglehub` and copies the SQLite database into `data/raw/`. If the
file is already there it does nothing. Kaggle credentials are read by `kagglehub` from
`KAGGLE_USERNAME` / `KAGGLE_KEY` and are never stored in the repository.

### 6.5 `src/us_wildfires_big_data/etl/transform.py`

Reads the `Fires` table in chunks of 100,000 rows (so the 800 MB database never has to fit in
memory at once) and writes `data/processed/fires.csv`:

- Keeps 15 of the original columns.
- `julian_to_date` converts the julian `DISCOVERY_DATE` into `discovery_date`.
- `hhmm_to_hour` converts the `HHMM` `DISCOVERY_TIME` into `discovery_hour` (0–23).
  **47% of the fires have no discovery time**; their hour stays null instead of being filled
  with 00:00. Filling it would mix them with the 667 real midnight fires and create a false
  peak at 00:00 in any hourly analysis.
- `julian_to_iso` converts the containment date and time into `cont_dt`.
- Drops rows without coordinates and lowercases the column names.

Test: `tests/test_transform.py`.

### 6.6 `notebooks/Exploratory_data_analysis.ipynb`

Read the notebook before `clean.py`: it explores `fires.csv` and justifies each cleaning
decision that `clean.py` applies with Dask:

- `county` mixes FIPS codes and names (the most common value is `"5"`) and has 678,148 nulls.
  A spatial join against the US Census county map fills it and leaves only 1,940 nulls.
- `fire_name` is only a label and `cont_dt` has 891,531 nulls, so both are dropped.
- The remaining 1,940 rows without a county are dropped.

The notebook is exploratory and does not run as part of the pipeline. Its saved outputs were
produced before the date change, so they still show a single `discovery_dt` column.

### 6.7 `src/us_wildfires_big_data/etl/geojson.py`

Pure functions (no files, no database), used by `clean.py` and `load_mongo.py`:

- `valid_coordinates(pdf)`: mask of rows with latitude within ±90 and longitude within ±180.
  Nulls are rejected too. The `2dsphere` index would reject those points.
- `row_to_feature(row)`: builds one GeoJSON Feature. Coordinates go as `[longitude, latitude]`,
  `fod_id` becomes the `_id`, and every other column goes into `properties`.
- `partition_to_features(pdf)`: converts a whole partition. It turns numpy numbers into Python
  numbers and `NaN`/`NaT`/`<NA>` into `None`, because pymongo does not accept numpy types.

Test: `tests/test_geojson.py`.

### 6.8 `src/us_wildfires_big_data/etl/cluster.py`

`dask_client()` decides where the Dask work runs. Both Dask scripts wrap their work in
`with dask_client() as client:`, and every computation inside that block runs on the cluster:

- If `DASK_SCHEDULER` is set (Docker Compose sets it), it connects to that scheduler and waits
  for at least one worker.
- Otherwise it starts a `LocalCluster`: one scheduler and `DASK_WORKERS` single-threaded
  workers, one per logical processor by default.

`worker_count(client)` returns how many workers are connected. The scripts print the dashboard
link, where you can watch each worker's progress and memory.

### 6.9 `src/us_wildfires_big_data/etl/clean.py`

The Dask cleaning stage. `main` downloads the county map once (`download_counties`), then
inside `dask_client()`:

1. Reads `fires.csv` with `dd.read_csv` in 16 MB blocks (about 12 partitions, so every worker
   gets work). Column types are declared up front so every partition has the same schema.
2. Applies `clean_partition` to every partition with `map_partitions`:
   1. Drops rows with invalid coordinates (`valid_coordinates`).
   2. Fills `county` with `assign_county`: a GeoPandas spatial join (`within`) between the fire
      points (NAD83, `EPSG:4269`) and the county polygons. If a point matches two counties, only
      the first match is kept, so no fire is duplicated.
   3. Drops `fire_name` and `cont_dt`.
   4. Drops the rows that still have no county.
3. Writes `fires_clean.parquet`. Parquet keeps the column types (dates, nullable hour), which
   a CSV would lose.

The county map is wrapped in `dask.delayed`, so it is sent to the workers once and shared by
every partition instead of being copied into each task.

Test: `tests/test_clean.py` (uses two small square "counties" instead of the real map).

### 6.10 `src/us_wildfires_big_data/etl/load_mongo.py`

Loads `fires_clean.parquet` into MongoDB. Inside `dask_client()`, `main`:

1. Repartitions the data so there are at least as many partitions as connected workers.
2. Calls `create_indexes`: the `2dsphere` index on `geometry` and an index on
   `properties.discovery_date`, **before** loading, so MongoDB validates every point.
3. Runs `load_partition` on every partition. Each one converts its rows with
   `partition_to_features` and writes them in batches of `MONGO_BATCH_SIZE` with `bulk_write`
   and `ReplaceOne(upsert=True)` (`ordered=False`, so one failed document doesn't stop the rest of the batch).
   Each partition opens its own `MongoClient`, because a client cannot be sent between processes.
4. Prints how many features were loaded and how many documents the collection holds.

A stored document:

```json
{
  "_id": 1,
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [-121.00583333, 40.03694444] },
  "properties": {
    "fod_id": 1, "fire_year": 2005, "stat_cause_descr": "Miscellaneous",
    "fire_size": 0.1, "fire_size_class": "A", "owner_descr": "USFS",
    "state": "CA", "county": "Plumas",
    "discovery_date": "2005-02-02T00:00:00", "discovery_hour": 13
  }
}
```

### 6.11 `src/us_wildfires_big_data/etl/pipeline.py`

Runs the four steps in order by calling each module's `main()`. It is what `docker compose up`
runs (`etl` service) and what `uv run us-wildfires-big-data` runs locally (`[project.scripts]` in
`pyproject.toml`).

A step is skipped when its output already exists: the SQLite database, `fires.csv`,
`fires_clean.parquet`, or a collection that already holds as many documents as the Parquet has
rows (`mongo_is_loaded`). So starting the system a second time takes seconds instead of
re-processing everything. To redo a step, delete its output or run its module directly.

### 6.12 `docker/dask.Dockerfile` and `docker-compose.yml`

`docker/dask.Dockerfile` builds one image with the project and its locked dependencies
(`uv sync --locked --no-dev`). The scheduler, the workers and the ETL runner all use it,
because Dask requires the client and the workers to run the same Python and library versions,
and the workers must be able to import the project code.

`docker-compose.yml` defines:

| Service | What it does |
|---|---|
| `mongo` | MongoDB 8.0 on port 27017, data kept in the `mongo-data` volume |
| `dask-scheduler` | `dask scheduler` on port 8786, dashboard on http://localhost:8787 |
| `dask-worker` | 2 containers, each with `nproc / 2` single-threaded workers, so one worker per logical processor in total. `DASK_NWORKERS` overrides the number per container |
| `etl` | Runs `etl/pipeline.py` once and exits. It starts after MongoDB passes its health check and the workers have started. A single step can be run with `docker compose run --rm etl python -m ...` |

Every project container mounts `./data` at `/app/data` and gets `DATA_DIR=/app/data`,
`MONGO_URI=mongodb://mongo:27017` and `DASK_SCHEDULER=tcp://dask-scheduler:8786`. The workers
read the files and write to MongoDB themselves, so they must see the same paths and addresses
as the script that sends them the work.

### 6.13 `tests/`

`uv run pytest` runs 8 tests on the pure functions (`transform`, `geojson`, `clean`). They need
neither the dataset nor MongoDB, so they run in about a second.

## 7. Columns at each stage

| Column | fires.csv | fires_clean.parquet / MongoDB |
|---|---|---|
| `fod_id` | ✓ | ✓ (also the MongoDB `_id`) |
| `fire_name` | ✓ (51% null) | dropped |
| `fire_year` | ✓ | ✓ |
| `stat_cause_descr` | ✓ | ✓ |
| `fire_size`, `fire_size_class` | ✓ | ✓ |
| `owner_descr` | ✓ | ✓ |
| `state` | ✓ | ✓ |
| `county` | codes and names mixed, 36% null | county name from the spatial join, no nulls |
| `latitude`, `longitude` | ✓ | ✓ in Parquet; `geometry.coordinates` in MongoDB |
| `discovery_date` | ✓ | ✓ |
| `discovery_hour` | 0–23, null when unknown | 0–23, null when unknown (46.9%) |
| `cont_dt` | ✓ (47% null) | dropped |

## 8. Decisions and their reasons

| Decision | Reason |
|---|---|
| Drop null or out-of-range coordinates | The `2dsphere` index rejects them; none were found in this dataset, but the check protects the load |
| Fill `county` with a spatial join | The original column mixes FIPS codes and names and is 36% null; the join leaves 1,940 nulls |
| Drop the 1,940 rows without county | 0.1% of the data; their points fall outside every county polygon |
| Drop `fire_name` and `cont_dt` | A label with no analytical value, and a column that is 47% null |
| Keep unknown discovery hours as null | Filling with 00:00 creates a false midnight peak; dropping would lose 47% of the fires |
| Parquet between clean and load | Keeps dates and nullable integers typed, unlike CSV |
| `fod_id` as `_id` + upsert | Re-running the load never duplicates records |
| Index before loading | MongoDB validates every point as it is inserted |
| One worker per logical processor, one thread each | Uses every processor without workers competing for the same one |
| At least one partition per worker | Otherwise some workers stay idle |

## 9. How to check that it worked

After the load, from Python (`uv run python`):

```python
from pymongo import MongoClient

fires = MongoClient("mongodb://localhost:27017").wildfires.fires
fires.count_documents({})                      # 1,878,525
[i["key"] for i in fires.list_indexes()]       # _id, geometry: 2dsphere, properties.discovery_date

point = {"type": "Point", "coordinates": [-121.0, 40.0]}   # [longitude, latitude]

# Fires within 5 km of a point
len(list(fires.find({"geometry": {"$near": {"$geometry": point, "$maxDistance": 5000}}})))   # 97

# Fires inside a polygon
polygon = {"type": "Polygon", "coordinates": [[[-122, 39], [-120, 39], [-120, 41], [-122, 41], [-122, 39]]]}
fires.count_documents({"geometry": {"$geoWithin": {"$geometry": polygon}}})   # 23,179

# Nearest fires with their distance in metres
list(fires.aggregate([
    {"$geoNear": {"near": point, "distanceField": "dist", "maxDistance": 5000}},
    {"$limit": 3},
]))
```

These were run against a full load: `$near` with a 5 km radius returns 97 fires, and the
nearest fire to `(-121, 40)` is 94 m away, in Plumas county.

## 10. Current status

| Part | Status |
|---|---|
| Download, transform, clean | Run on the full dataset |
| Load into MongoDB with `2dsphere` index | Run on the full dataset against MongoDB 8.0, with a local cluster and with a separate scheduler + 2 worker processes (8 workers); re-running doesn't duplicate |
| One-command pipeline (`etl/pipeline.py`) | Run from an empty data folder to a loaded MongoDB in 1 min 36 s (download skipped, SQLite already present); a second run skips every step in 3 s |
| `docker compose up --build` (image build and services) | Written but not yet run, because Docker was not available in the development environment |
