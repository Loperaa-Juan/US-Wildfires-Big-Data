"""SparkSession connected to MongoDB through the MongoDB Spark Connector."""

from pyspark.sql import SparkSession

from us_wildfires_big_data.config import (
    MONGO_COLLECTION,
    MONGO_DB,
    MONGO_SPARK_CONNECTOR,
    MONGO_URI,
    SPARK_DRIVER_MEMORY,
    SPARK_MASTER,
)


def create_spark_session(app_name: str = "USWildfiresSparkAnalysis") -> SparkSession:
    """Spark reads and writes MONGO_DB by default; the collection is chosen per read/write."""
    return (
        SparkSession.builder.appName(app_name)
        .master(SPARK_MASTER)
        # Downloaded from Maven the first time the session starts
        .config("spark.jars.packages", MONGO_SPARK_CONNECTOR)
        .config("spark.mongodb.read.connection.uri", MONGO_URI)
        .config("spark.mongodb.read.database", MONGO_DB)
        .config("spark.mongodb.read.collection", MONGO_COLLECTION)
        .config("spark.mongodb.write.connection.uri", MONGO_URI)
        .config("spark.mongodb.write.database", MONGO_DB)
        .config("spark.driver.memory", SPARK_DRIVER_MEMORY)
        .getOrCreate()
    )
