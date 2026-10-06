"""
Spark stage: reads the GeoJSON fires from MongoDB (loaded by etl/load_mongo.py) with the
MongoDB Spark Connector, computes spatial and temporal aggregations on the Spark cluster and
saves each result in its own MongoDB collection (replacing it if it already exists).

| Collection         | One document per                                         |
|--------------------|----------------------------------------------------------|
| fires_by_grid      | grid cell with fires (GRID_CELL_DEGREES side), + polygon |
| fires_hotspots     | grid cell with z-score >= HOTSPOT_MIN_ZSCORE, ranked     |
| fires_by_hour      | discovery hour 0-23 (fires without a time are left out)  |
| fires_by_weekday   | day of the week (1 = Sunday)                             |
| fires_by_month     | month 1-12                                               |
| fires_by_year      | year 1992-2015                                           |
| fires_by_state     | state                                                    |
| fires_by_cause     | cause                                                    |

Run it with `python -m us_wildfires_big_data.spark.analysis` (the `spark` service in
docker-compose does it). Settings come from us_wildfires_big_data.config (see .env.example).
"""

import time

from pymongo import GEOSPHERE, MongoClient
from pyspark import StorageLevel
from pyspark.sql import DataFrame

from us_wildfires_big_data.config import (
    GRID_CELL_DEGREES,
    HOTSPOT_MIN_ZSCORE,
    MONGO_DB,
    MONGO_URI,
)
from us_wildfires_big_data.spark import aggregations as agg
from us_wildfires_big_data.spark.session import create_spark_session

# Collections whose `geometry` is a cell polygon; they get a 2dsphere index
GEO_COLLECTIONS = ["fires_by_grid", "fires_hotspots"]


def save(df: DataFrame, collection: str) -> int:
    """Replace `collection` with the rows of `df` and return how many were written."""
    start = time.perf_counter()
    df = df.cache()  # counted and written: computed once
    rows = df.count()
    df.write.format("mongodb").mode("overwrite").option("collection", collection).save()
    df.unpersist()
    print(
        f"  {collection:<18} {rows:>6,} documents  {time.perf_counter() - start:6.1f} s"
    )
    return rows


def create_geo_indexes() -> None:
    with MongoClient(MONGO_URI) as client:
        for name in GEO_COLLECTIONS:
            client[MONGO_DB][name].create_index([("geometry", GEOSPHERE)])


def main() -> None:
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")
    try:
        print(f"Spark {spark.version} on {spark.sparkContext.master}")
        print(f"Spark UI: {spark.sparkContext.uiWebUrl}")

        fires = agg.flatten(
            spark.read.format("mongodb").schema(agg.FIRES_SCHEMA).load()
        )
        # Every aggregation below reads the fires, so they are read from MongoDB only once
        fires = fires.persist(StorageLevel.MEMORY_AND_DISK)
        print(f"Read {fires.count():,} fires from MongoDB")

        print("Saving aggregations:")
        grid = agg.grid_counts(fires, GRID_CELL_DEGREES).cache()
        save(grid, "fires_by_grid")
        save(agg.hotspots(grid, HOTSPOT_MIN_ZSCORE), "fires_hotspots")
        save(agg.by_hour(fires), "fires_by_hour")
        save(agg.by_weekday(fires), "fires_by_weekday")
        save(agg.by_month(fires), "fires_by_month")
        save(agg.by_year(fires), "fires_by_year")
        save(agg.by_state(fires), "fires_by_state")
        save(agg.by_cause(fires), "fires_by_cause")
        create_geo_indexes()

        print(f"\nTop 5 hotspots ({GRID_CELL_DEGREES}° cells):")
        hot = spark.read.format("mongodb").option("collection", "fires_hotspots").load()
        hot.orderBy("rank").select(
            "rank", "fires", "zscore", "acres_burned", "center.coordinates"
        ).show(5, truncate=False)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
