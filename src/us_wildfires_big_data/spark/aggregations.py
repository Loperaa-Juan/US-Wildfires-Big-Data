"""Spatial and temporal aggregations of the fires. Pure DataFrame -> DataFrame functions: no
MongoDB and no SparkSession settings, so they can be tested on small hand-made DataFrames.

Every result has an `_id` (the group key), so writing it to MongoDB gives one document per
group, and the same three statistics (`_fire_stats`).
"""

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# Schema of the documents written by etl/load_mongo.py. Declaring it avoids the connector's
# schema inference, which samples documents and can guess wrong types for mostly-null fields
# (discovery_hour is null in 47% of the fires).
FIRES_SCHEMA = StructType(
    [
        StructField("_id", LongType()),
        StructField(
            "geometry",
            StructType(
                [
                    StructField("type", StringType()),
                    StructField("coordinates", ArrayType(DoubleType())),
                ]
            ),
        ),
        StructField(
            "properties",
            StructType(
                [
                    StructField("fire_year", IntegerType()),
                    StructField("stat_cause_descr", StringType()),
                    StructField("fire_size", DoubleType()),
                    StructField("fire_size_class", StringType()),
                    StructField("owner_descr", StringType()),
                    StructField("state", StringType()),
                    StructField("county", StringType()),
                    StructField("discovery_date", TimestampType()),
                    StructField("discovery_hour", IntegerType()),
                ]
            ),
        ),
    ]
)

WEEKDAYS = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]
MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def flatten(fires: DataFrame) -> DataFrame:
    """GeoJSON Features -> one flat row per fire, with longitude and latitude columns."""
    coordinates = F.col("geometry.coordinates")
    return fires.select(
        F.col("_id").alias("fod_id"),
        coordinates[0].alias("longitude"),  # GeoJSON order is [longitude, latitude]
        coordinates[1].alias("latitude"),
        "properties.*",
    )


def _fire_stats() -> list[Column]:
    return [
        F.count("*").alias("fires"),
        F.round(F.sum("fire_size"), 2).alias("acres_burned"),
        F.round(F.avg("fire_size"), 2).alias("avg_acres"),
    ]


def _point(lon: Column, lat: Column) -> Column:
    return F.struct(
        F.lit("Point").alias("type"), F.array(lon, lat).alias("coordinates")
    )


def _rectangle(west: Column, south: Column, east: Column, north: Column) -> Column:
    """GeoJSON Polygon of a grid cell: one closed ring, counterclockwise as GeoJSON expects."""
    ring = F.array(
        F.array(west, south),
        F.array(east, south),
        F.array(east, north),
        F.array(west, north),
        F.array(west, south),
    )
    return F.struct(F.lit("Polygon").alias("type"), F.array(ring).alias("coordinates"))


def grid_counts(fires: DataFrame, cell_degrees: float) -> DataFrame:
    """Fires per square grid cell of `cell_degrees` side. Only cells with fires appear.

    A fire at (lon, lat) falls in cell (floor(lon / size), floor(lat / size)); the cell is
    stored with its GeoJSON polygon (`geometry`) and its center point (`center`).
    """
    size = F.lit(cell_degrees)
    cells = fires.groupBy(
        F.floor(F.col("longitude") / size).alias("cell_x"),
        F.floor(F.col("latitude") / size).alias("cell_y"),
    ).agg(*_fire_stats())

    # Rounded so that 0.1-degree cells give -120.3 and not -120.30000000000001
    west = F.round(F.col("cell_x") * size, 6)
    south = F.round(F.col("cell_y") * size, 6)
    east = F.round((F.col("cell_x") + 1) * size, 6)
    north = F.round((F.col("cell_y") + 1) * size, 6)
    return cells.select(
        F.concat_ws("_", "cell_x", "cell_y").alias("_id"),
        "cell_x",
        "cell_y",
        "fires",
        "acres_burned",
        "avg_acres",
        _rectangle(west, south, east, north).alias("geometry"),
        _point(F.round((west + east) / 2, 6), F.round((south + north) / 2, 6)).alias(
            "center"
        ),
    )


def hotspots(grid: DataFrame, min_zscore: float) -> DataFrame:
    """Cells whose fire count is at least `min_zscore` standard deviations above the mean.

    The mean and standard deviation are taken over the cells that have fires, so a hotspot is
    a cell that is unusually dense compared with the rest of the burned area. `rank` 1 is the
    cell with most fires.
    """
    stats = grid.agg(
        F.avg("fires").alias("mean_fires"), F.stddev_pop("fires").alias("std_fires")
    )
    scored = grid.crossJoin(stats).withColumn(
        "zscore",
        F.round((F.col("fires") - F.col("mean_fires")) / F.col("std_fires"), 2),
    )
    # The window has no partitions, but it only sees the few hotspot cells
    by_fires = Window.orderBy(F.col("fires").desc(), F.col("_id"))
    return (
        scored.filter(F.col("zscore") >= min_zscore)
        .withColumn("rank", F.row_number().over(by_fires))
        .drop("mean_fires", "std_fires")
    )


def counts_by(fires: DataFrame, key: str, value: Column) -> DataFrame:
    """Fire statistics grouped by `value`, stored in a column named `key`. Null keys are left
    out (e.g. the 47% of fires without a discovery hour are not counted by hour)."""
    return (
        fires.filter(value.isNotNull())
        .groupBy(value.alias(key))
        .agg(*_fire_stats())
        .withColumn("_id", F.col(key))
    )


def _with_name(df: DataFrame, key: str, names: list[str]) -> DataFrame:
    """Add `name`: names[key - 1], for keys numbered from 1 (weekday, month)."""
    return df.withColumn(
        "name", F.element_at(F.array(*[F.lit(n) for n in names]), F.col(key))
    )


def by_hour(fires: DataFrame) -> DataFrame:
    return counts_by(fires, "hour", F.col("discovery_hour"))


def by_weekday(fires: DataFrame) -> DataFrame:
    # dayofweek: 1 = Sunday ... 7 = Saturday
    days = counts_by(fires, "weekday", F.dayofweek("discovery_date"))
    return _with_name(days, "weekday", WEEKDAYS)


def by_month(fires: DataFrame) -> DataFrame:
    months = counts_by(fires, "month", F.month("discovery_date"))
    return _with_name(months, "month", MONTHS)


def by_year(fires: DataFrame) -> DataFrame:
    return counts_by(fires, "year", F.col("fire_year"))


def by_state(fires: DataFrame) -> DataFrame:
    return counts_by(fires, "state", F.col("state"))


def by_cause(fires: DataFrame) -> DataFrame:
    return counts_by(fires, "cause", F.col("stat_cause_descr"))
