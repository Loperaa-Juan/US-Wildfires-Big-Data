"""SparkSession connected to MongoDB through the MongoDB Spark Connector."""

import socket

from pyspark.sql import SparkSession

from us_wildfires_big_data.config import (
    MONGO_COLLECTION,
    MONGO_DB,
    MONGO_SPARK_CONNECTOR,
    MONGO_URI,
    SPARK_DRIVER_HOST,
    SPARK_DRIVER_MEMORY,
    SPARK_EXECUTOR_MEMORY,
    SPARK_MASTER,
)


def create_spark_session(app_name: str = "USWildfiresSparkAnalysis") -> SparkSession:
    """Spark reads and writes MONGO_DB by default; the collection is chosen per read/write."""
    builder = (
        SparkSession.builder.appName(app_name)
        .master(SPARK_MASTER)
        # Downloaded from Maven the first time the session starts, then shipped to the executors
        .config("spark.jars.packages", MONGO_SPARK_CONNECTOR)
        .config("spark.mongodb.read.connection.uri", MONGO_URI)
        .config("spark.mongodb.read.database", MONGO_DB)
        .config("spark.mongodb.read.collection", MONGO_COLLECTION)
        .config("spark.mongodb.write.connection.uri", MONGO_URI)
        .config("spark.mongodb.write.database", MONGO_DB)
        .config("spark.driver.memory", SPARK_DRIVER_MEMORY)
        .config("spark.executor.memory", SPARK_EXECUTOR_MEMORY)
        # Dates are stored in MongoDB as UTC midnights; reading them in another time zone would
        # shift them to the previous day and break the weekday and month aggregations
        .config("spark.sql.session.timeZone", "UTC")
        # The console progress bars flood the docker / Jenkins logs; the UI shows progress
        .config("spark.ui.showConsoleProgress", "false")
    )
    if SPARK_MASTER.startswith("spark://"):
        # In a cluster the executors open connections back to the driver, so it must listen on
        # every interface and advertise an address they can reach: by default its own IP, which
        # works both for `docker compose up` and `docker compose run`
        host = SPARK_DRIVER_HOST or socket.gethostbyname(socket.gethostname())
        builder = builder.config("spark.driver.host", host).config(
            "spark.driver.bindAddress", "0.0.0.0"
        )
    return builder.getOrCreate()
