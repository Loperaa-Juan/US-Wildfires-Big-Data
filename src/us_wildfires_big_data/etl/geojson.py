"""Rows -> GeoJSON Features. Pure functions: no files, no MongoDB."""

from __future__ import annotations

import pandas as pd

# Column names as written by etl/transform.py 
LAT, LON, ID = "latitude", "longitude", "fod_id"


def valid_coordinates(pdf: pd.DataFrame) -> pd.Series:
    """Boolean mask of rows whose coordinates are present and inside WGS84 range.

    The 2dsphere index rejects points outside [-180, 180] x [-90, 90], so those rows
    are dropped before loading instead of failing the whole batch.
    """
    lat, lon = pdf[LAT], pdf[LON]
    return lat.between(-90, 90) & lon.between(-180, 180)  # NaN -> False


def row_to_feature(row: dict) -> dict:
    """{'fod_id': 1, 'latitude': 40.0, 'longitude': -121.0, ...} -> GeoJSON Feature."""
    props = dict(row)  # copy: the input is not modified
    lat, lon = props.pop(LAT), props.pop(LON)
    return {
        "_id": int(props[ID]),  # reloading upserts instead of duplicating records
        "type": "Feature",
        # GeoJSON requires [longitude, latitude], in that order
        "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
        "properties": props,
    }


def partition_to_features(pdf: pd.DataFrame) -> list[dict]:
    """Convert a whole (pandas) partition.

    astype(object) turns numpy.int64/float64 into Python int/float (pymongo rejects numpy)
    and where(...) replaces NaN/NaT with None.
    """
    pdf = pdf.astype(object).where(pdf.notna(), None)
    return [row_to_feature(r) for r in pdf.to_dict("records")]
