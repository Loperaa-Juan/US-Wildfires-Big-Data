import math

import numpy as np
import pandas as pd

from us_wildfires_big_data.etl.geojson import (
    partition_to_features,
    row_to_feature,
    valid_coordinates,
)


def test_row_to_feature_builds_point_in_lon_lat_order():
    row = {"fod_id": 1, "latitude": 40.0, "longitude": -121.0, "state": "CA"}

    feature = row_to_feature(row)

    assert feature == {
        "_id": 1,
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-121.0, 40.0]},
        "properties": {"fod_id": 1, "state": "CA"},
    }
    assert "latitude" in row  # input left untouched


def test_partition_to_features_converts_numpy_and_missing_values():
    pdf = pd.DataFrame(
        {
            "fod_id": np.array([1, 2], dtype="int64"),
            "fire_name": ["FOUNTAIN", None],
            "fire_size": [0.1, np.nan],
            "latitude": [40.0, 38.9],
            "longitude": [-121.0, -120.4],
            "discovery_date": pd.to_datetime(["2005-02-02", None]),
            "discovery_hour": pd.array([13, None], dtype="Int64"),
        }
    )

    first, second = partition_to_features(pdf)

    assert type(first["_id"]) is int
    assert type(first["properties"]["fod_id"]) is int
    assert type(first["properties"]["fire_size"]) is float
    assert all(type(c) is float for c in first["geometry"]["coordinates"])
    assert first["properties"]["discovery_date"] == pd.Timestamp("2005-02-02")
    assert type(first["properties"]["discovery_hour"]) is int
    assert second["properties"]["fire_name"] is None
    assert second["properties"]["fire_size"] is None
    assert second["properties"]["discovery_date"] is None
    assert second["properties"]["discovery_hour"] is None


def test_valid_coordinates_drops_null_and_out_of_range():
    pdf = pd.DataFrame(
        {
            "latitude": [40.0, math.nan, 95.0, 10.0, -90.0],
            "longitude": [-121.0, -120.0, -120.0, -200.0, 180.0],
        }
    )

    assert valid_coordinates(pdf).tolist() == [True, False, False, False, True]
