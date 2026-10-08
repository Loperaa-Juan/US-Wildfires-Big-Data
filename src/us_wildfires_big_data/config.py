import os
from pathlib import Path

# Repository root: src/us_wildfires_big_data/config.py -> ../../
ROOT = Path(__file__).resolve().parents[2]

# Data paths
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
RAW_DATA = DATA_DIR / "raw"
PROCESSED_DATA = DATA_DIR / "processed"
SQLITE_PATH = RAW_DATA / "FPA_FOD_20170508.sqlite"
FIRES_CSV = PROCESSED_DATA / "fires.csv"

# Kaggle dataset
KAGGLE_DATASET = os.getenv("KAGGLE_DATASET", "rtatman/188-million-us-wildfires")

# MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "wildfires")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "fires")
MONGO_BATCH_SIZE = int(os.getenv("MONGO_BATCH_SIZE", "5000"))

# Cleaned dataset (written by etl/clean.py, read by etl/load_mongo.py)
FIRES_CLEAN = PROCESSED_DATA / "fires_clean.parquet"

# US Census county boundaries, used to fill the county column
COUNTIES_URL = os.getenv(
    "COUNTIES_URL",
    "https://www2.census.gov/geo/tiger/GENZ2021/shp/cb_2021_us_county_20m.zip",
)
COUNTIES_ZIP = RAW_DATA / "cb_2021_us_county_20m.zip"

# Dask: address of a running scheduler (set by docker-compose). When it is empty the scripts
# start a local cluster with DASK_WORKERS workers, one per logical processor by default
DASK_SCHEDULER = os.getenv("DASK_SCHEDULER")
DASK_WORKERS = int(os.getenv("DASK_WORKERS", os.cpu_count() or 1))

# Spark: master URL (local[*] runs Spark inside the driver's process) and the MongoDB connector.
# The connector must match the Scala version of pyspark: Spark 4 is built with Scala 2.13 and
# needs connector 11.x (10.x is for Spark 3 / Scala 2.12)
SPARK_MASTER = os.getenv("SPARK_MASTER", "local[*]")
SPARK_DRIVER_MEMORY = os.getenv("SPARK_DRIVER_MEMORY", "4g")
SPARK_EXECUTOR_MEMORY = os.getenv("SPARK_EXECUTOR_MEMORY", "2g")
# Address the executors use to reach the driver in a cluster; defaults to the driver's own IP
SPARK_DRIVER_HOST = os.getenv("SPARK_DRIVER_HOST")
MONGO_SPARK_CONNECTOR = os.getenv(
    "MONGO_SPARK_CONNECTOR", "org.mongodb.spark:mongo-spark-connector_2.13:11.1.0"
)

# Spark aggregations: side of each grid cell in degrees (0.5° ≈ 55 km of latitude), and the
# z-score a cell's fire count must reach to count as a hotspot (mean + 2 std by default)
GRID_CELL_DEGREES = float(os.getenv("GRID_CELL_DEGREES", "0.5"))
HOTSPOT_MIN_ZSCORE = float(os.getenv("HOTSPOT_MIN_ZSCORE", "2"))
