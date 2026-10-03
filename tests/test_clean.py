import math

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from us_wildfires_big_data.etl.clean import clean_partition

# Two adjacent square "counties" sharing the border at longitude -120
COUNTIES = gpd.GeoDataFrame(
    {"NAME": ["West", "East"]},
    geometry=[box(-122, 38, -120, 40), box(-120, 38, -118, 40)],
    crs="EPSG:4269",
)


def make_partition(**overrides):
    rows = {
        "fod_id": [1, 2, 3, 4, 5],
        "fire_name": ["A", None, "C", "D", "E"],
        "county": ["5", None, "Lake", None, None],
        "latitude": [39.0, 39.0, 39.0, math.nan, 39.0],
        "longitude": [-121.0, -119.0, -110.0, -121.0, -200.0],
        "cont_dt": [None, None, None, None, None],
    }
    return pd.DataFrame(rows | overrides)


def test_clean_partition_fills_county_from_coordinates():
    clean = clean_partition(make_partition(), COUNTIES)

    # 3: outside every county, 4: null latitude, 5: longitude out of range
    assert clean["fod_id"].tolist() == [1, 2]
    assert clean["county"].tolist() == ["West", "East"]


def test_clean_partition_drops_unused_columns():
    clean = clean_partition(make_partition(), COUNTIES)

    assert "fire_name" not in clean.columns
    assert "cont_dt" not in clean.columns


def test_point_matching_two_counties_is_not_duplicated():
    overlapping = gpd.GeoDataFrame(
        {"NAME": ["First", "Second"]},
        geometry=[box(-122, 38, -120, 40), box(-121.5, 38, -118, 40)],
        crs="EPSG:4269",
    )

    clean = clean_partition(make_partition(), overlapping)

    assert clean["fod_id"].tolist() == [1, 2]
    assert clean["county"].tolist() == ["First", "Second"]
