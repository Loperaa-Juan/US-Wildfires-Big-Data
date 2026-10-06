"""Spark aggregations on a handful of hand-made fires. They need pyspark (`uv sync --extra
spark`) and Java 17+; without them the tests are skipped."""

import shutil
import subprocess
from datetime import UTC, datetime

import pytest

pytest.importorskip("pyspark")
from pyspark.sql import SparkSession

from us_wildfires_big_data.spark import aggregations as agg


def java_version() -> int:
    if not shutil.which("java"):
        return 0
    out = subprocess.run(
        ["java", "-version"], capture_output=True, text=True, check=False
    ).stderr
    # 'openjdk version "17.0.2"' -> 17, 'openjdk version "1.8.0_402"' -> 1
    return int(out.split('"')[1].split(".")[0])


pytestmark = pytest.mark.skipif(java_version() < 17, reason="Spark 4 needs Java 17+")


@pytest.fixture(scope="module")
def spark():
    session = (
        SparkSession.builder.master("local[1]")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()


def feature(
    fod_id, lon, lat, hour=None, date=datetime(2005, 2, 2, tzinfo=UTC), size=1.0
):
    """One document as etl/load_mongo.py stores it. 2005-02-02 was a Wednesday."""
    props = (2005, "Lightning", size, "A", "USFS", "CA", "Plumas", date, hour)
    return (fod_id, ("Point", [lon, lat]), props)


@pytest.fixture(scope="module")
def fires(spark):
    rows = [
        feature(1, -120.9, 40.1, hour=13, size=2.0),  # cell (-242, 80)
        feature(2, -120.6, 40.4, hour=13, size=4.0),  # cell (-242, 80)
        feature(
            3, -120.4, 40.1, hour=8, date=datetime(2005, 7, 3, tzinfo=UTC)
        ),  # cell (-241, 80)
        feature(4, -100.0, 35.0),  # cell (-200, 70), no hour
    ]
    return agg.flatten(spark.createDataFrame(rows, agg.FIRES_SCHEMA))


def by_id(df):
    return {r["_id"]: r for r in df.collect()}


def test_flatten_keeps_geojson_order(fires):
    first = fires.filter("fod_id = 1").first()
    assert (first.longitude, first.latitude) == (-120.9, 40.1)
    assert first.state == "CA"


def test_grid_counts_fires_per_cell(fires):
    cells = by_id(agg.grid_counts(fires, 0.5))
    assert {k: c.fires for k, c in cells.items()} == {
        "-242_80": 2,
        "-241_80": 1,
        "-200_70": 1,
    }
    assert cells["-242_80"].acres_burned == 6.0
    assert cells["-242_80"].avg_acres == 3.0


def test_grid_cell_geometry_is_closed_rectangle(fires):
    cell = by_id(agg.grid_counts(fires, 0.5))["-242_80"]
    ring = cell.geometry.coordinates[0]
    assert cell.geometry.type == "Polygon"
    assert ring[0] == ring[-1] == [-121.0, 40.0]
    assert ring[2] == [-120.5, 40.5]
    assert cell.center.coordinates == [-120.75, 40.25]


def test_hotspots_keep_only_dense_cells(spark, fires):
    # Counts 2, 1, 1: mean 1.33, std 0.47 -> z-scores 1.41, -0.71, -0.71
    hot = agg.hotspots(agg.grid_counts(fires, 0.5), min_zscore=1).collect()
    assert [(h._id, h.rank, h.zscore) for h in hot] == [("-242_80", 1, 1.41)]


def test_by_hour_leaves_out_fires_without_time(fires):
    assert {k: r.fires for k, r in by_id(agg.by_hour(fires)).items()} == {13: 2, 8: 1}


def test_by_weekday_and_month_names(fires):
    days = by_id(agg.by_weekday(fires))
    assert days[4].name == "Wednesday" and days[4].fires == 3  # 2005-02-02
    assert days[1].name == "Sunday" and days[1].fires == 1  # 2005-07-03
    months = by_id(agg.by_month(fires))
    assert (months[2].name, months[2].fires) == ("February", 3)
    assert (months[7].name, months[7].fires) == ("July", 1)
