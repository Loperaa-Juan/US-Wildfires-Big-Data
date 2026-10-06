"""Dask cluster used by the ETL scripts."""

from collections.abc import Iterator
from contextlib import contextmanager

from dask.distributed import Client, LocalCluster

from us_wildfires_big_data.config import DASK_SCHEDULER, DASK_WORKERS


@contextmanager
def dask_client() -> Iterator[Client]:
    """Connect to the docker-compose scheduler if DASK_SCHEDULER is set; otherwise start a
    local cluster with one single-threaded worker per logical processor.

    While the block runs, every dask.compute / .compute() call is executed on this cluster.
    """
    if DASK_SCHEDULER:
        with Client(DASK_SCHEDULER) as client:
            client.wait_for_workers(1)
            yield client
    else:
        with (
            LocalCluster(n_workers=DASK_WORKERS, threads_per_worker=1) as cluster,
            Client(cluster) as client,
        ):
            yield client


def shutdown_cluster() -> None:
    """Stop the docker-compose Dask scheduler and its workers, so their containers exit and do
    not hold memory and CPU while the Spark stage runs. Without DASK_SCHEDULER it does nothing:
    a local cluster already stops at the end of each `with dask_client()` block."""
    if DASK_SCHEDULER:
        Client(DASK_SCHEDULER).shutdown()


def worker_count(client: Client) -> int:
    return len(client.scheduler_info()["workers"])
