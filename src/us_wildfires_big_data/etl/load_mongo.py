"""
Loads clean Parquet dataset into MongoDB using Dask partitions safely.
"""

import dask
import dask.dataframe as dd
from dask.distributed import Client
from pymongo import MongoClient

from us_wildfires_big_data.config import (
    FIRES_CLEAN,
    MONGO_COLLECTION,
    MONGO_DB,
    MONGO_URI,
)


def load_partition(df):
    """Inserts a single partition into MongoDB in smaller sub-batches to prevent OOM."""
    if df.empty:
        return 0

    records = df.to_dict(orient="records")
    batch_size = 5000
    total = 0

    with MongoClient(MONGO_URI) as client:
        collection = client[MONGO_DB][MONGO_COLLECTION]
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            if batch:
                collection.insert_many(batch, ordered=False)
                total += len(batch)
    return total


def main():
    # 1. Conectar al cluster de Dask usando el hostname del servicio
    client = Client("tcp://dask-scheduler:8786")

    # 2. Cargar Parquet y re-particionar en 100 fragmentos ligeros
    ddf = dd.read_parquet(FIRES_CLEAN).repartition(npartitions=100)

    # 3. Convertir las particiones en tareas diferidas
    partitions = ddf.to_delayed()

    print(f"Loading {len(partitions)} partitions into MongoDB...")

    # 4. Procesar las particiones con el cliente de Dask
    delayed_tasks = [dask.delayed(load_partition)(p) for p in partitions]
    results = client.compute(delayed_tasks, sync=True)

    print(
        f"Successfully loaded {sum(results)} documents into {MONGO_DB}.{MONGO_COLLECTION}"
    )


if __name__ == "__main__":
    main()