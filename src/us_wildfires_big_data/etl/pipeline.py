"""
Runs the whole ingestion pipeline in order: download → transform → clean → load_mongo.

It is what `docker compose up` runs, and locally `uv run us-wildfires-big-data`.

A step is skipped when its output is already there, so starting the system again does not
redo the work. To rebuild a step, delete its output (data/processed/... or the MongoDB
collection) or run that step's module directly, e.g. `python -m us_wildfires_big_data.etl.clean`.
"""

from pymongo import MongoClient
import pyarrow.parquet as pq

from us_wildfires_big_data.config import (
    FIRES_CLEAN,
    FIRES_CSV,
    MONGO_COLLECTION,
    MONGO_DB,
    MONGO_URI,
)
from us_wildfires_big_data.etl import clean, download, load_mongo, transform


def mongo_is_loaded() -> bool:
    """True when the collection already holds every row of the clean dataset."""
    try:
        with MongoClient(MONGO_URI) as client:
            loaded = client[MONGO_DB][MONGO_COLLECTION].count_documents({})
        
        if loaded == 0 or not FIRES_CLEAN.exists():
            return False

        dataset = pq.ParquetDataset(FIRES_CLEAN)
        total_rows = sum(fragment.metadata.num_rows for fragment in dataset.fragments)
        
        return loaded == total_rows
    except Exception as e:
        print(f"Warning: Could not verify MongoDB row count ({e}). Proceeding to load.")
        return False


def main() -> None:
    print("[1/4] Download")
    download.main()

    print("[2/4] Transform")
    if FIRES_CSV.exists():
        print("Already present at:", FIRES_CSV)
    else:
        transform.main()

    print("[3/4] Clean (Dask)")
    if FIRES_CLEAN.exists():
        print("Already present at:", FIRES_CLEAN)
    else:
        clean.main()

    print("[4/4] Load into MongoDB (Dask)")
    if mongo_is_loaded():
        print(f"{MONGO_DB}.{MONGO_COLLECTION} already holds the clean dataset")
    else:
        load_mongo.main()

    print("Pipeline finished")


if __name__ == "__main__":
    main()