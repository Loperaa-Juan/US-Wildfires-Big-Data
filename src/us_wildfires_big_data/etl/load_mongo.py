"""
This script loads data/processed/fires_clean.parquet (written by etl/clean.py) into MongoDB
as GeoJSON Features.

- Runs on the Dask cluster (docker-compose scheduler, or a local one; see etl/cluster.py).
- Dask reads the clean dataset in partitions (at least one per worker); each partition is
  converted and written in batches by a worker.
- A 2dsphere index is created on `geometry` BEFORE loading, so MongoDB validates every point.
- Documents use fod_id as _id and are upserted, so re-running the script does not duplicate data.

Connection settings come from us_wildfires_big_data.config (see .env.example).
"""

import dask
import dask.dataframe as dd
import pandas as pd
from pymongo import ASCENDING, GEOSPHERE, MongoClient, ReplaceOne

from us_wildfires_big_data.config import (
    FIRES_CLEAN,
    MONGO_BATCH_SIZE,
    MONGO_COLLECTION,
    MONGO_DB,
    MONGO_URI,
)
from us_wildfires_big_data.etl.cluster import dask_client, worker_count
from us_wildfires_big_data.etl.geojson import partition_to_features


def create_indexes() -> None:
    with MongoClient(MONGO_URI) as client:
        fires = client[MONGO_DB][MONGO_COLLECTION]
        fires.create_index([("geometry", GEOSPHERE)])
        fires.create_index([("properties.discovery_date", ASCENDING)])


def load_partition(pdf: pd.DataFrame) -> int:
    """Convert and upsert one partition. Runs inside a Dask worker."""
    features = partition_to_features(pdf)
    # One client per partition: MongoClient objects cannot be shipped between workers
    with MongoClient(MONGO_URI) as client:
        fires = client[MONGO_DB][MONGO_COLLECTION]
        for start in range(0, len(features), MONGO_BATCH_SIZE):
            batch = features[start : start + MONGO_BATCH_SIZE]
            fires.bulk_write(
                [ReplaceOne({"_id": f["_id"]}, f, upsert=True) for f in batch],
                ordered=False,
            )
    return len(features)


def main() -> None:
    with dask_client() as client:
        workers = worker_count(client)
        print(f"Dask cluster with {workers} workers: {client.dashboard_link}")

        ddf = dd.read_parquet(FIRES_CLEAN)
        # Give every worker at least one partition, otherwise some of them stay idle
        ddf = ddf.repartition(npartitions=max(ddf.npartitions, workers))

        create_indexes()
        # Runs on the cluster because the Client above is the active scheduler
        counts = dask.compute(
            *[dask.delayed(load_partition)(p) for p in ddf.to_delayed()]
        )

    with MongoClient(MONGO_URI) as client:
        total = client[MONGO_DB][MONGO_COLLECTION].count_documents({})
    print(f"Loaded {sum(counts):,} features from {ddf.npartitions} partitions")
    print(f"Collection {MONGO_DB}.{MONGO_COLLECTION} now holds {total:,} documents")


if __name__ == "__main__":
    main()
