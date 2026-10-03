"""
This script cleans data/processed/fires.csv with Dask and writes data/processed/fires_clean.parquet.

The cleaning steps are the ones tested and justified in notebooks/Exploratory_data_analysis.ipynb:
1. Discard records with null or out-of-range coordinates (the 2dsphere index would reject them).
2. Fill the county column with a spatial join against the US Census county map, because the
   original column mixes FIPS codes and names (e.g. "5") and has 678,148 nulls.
3. Drop fire_name (only a label) and cont_dt (891,531 nulls).
4. Drop the few records that still have no county (points outside every county polygon).

It runs on the Dask cluster (see etl/cluster.py). The output is Parquet so the datetimes and dtypes survive for the MongoDB load.
"""

import urllib.request

import dask
import dask.dataframe as dd
import geopandas as gpd
import pandas as pd

from us_wildfires_big_data.config import (
    COUNTIES_URL,
    COUNTIES_ZIP,
    FIRES_CLEAN,
    FIRES_CSV,
)
from us_wildfires_big_data.etl.cluster import dask_client
from us_wildfires_big_data.etl.geojson import LAT, LON, valid_coordinates

DROP_COLUMNS = ["fire_name", "cont_dt"]

# The dataset's coordinates are in NAD83
FIRES_CRS = "EPSG:4269"


def download_counties() -> None:
    if COUNTIES_ZIP.exists():
        print("County map already present at:", COUNTIES_ZIP)
        return
    COUNTIES_ZIP.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(COUNTIES_URL, COUNTIES_ZIP)
    print("County map downloaded to:", COUNTIES_ZIP)


def assign_county(pdf: pd.DataFrame, counties: gpd.GeoDataFrame) -> pd.Series:
    """Name of the county polygon that contains each point (NaN if none does)."""
    points = gpd.GeoDataFrame(
        index=pdf.index,
        geometry=gpd.points_from_xy(pdf[LON], pdf[LAT]),
        crs=FIRES_CRS,
    ).to_crs(counties.crs)
    joined = gpd.sjoin(
        points, counties[["NAME", "geometry"]], how="left", predicate="within"
    )
    # A point on a shared border can match two counties: keep the first match
    return joined["NAME"][~joined.index.duplicated()].astype("string")


def clean_partition(pdf: pd.DataFrame, counties: gpd.GeoDataFrame) -> pd.DataFrame:
    """Apply every cleaning step to one (pandas) partition."""
    pdf = pdf[valid_coordinates(pdf)].reset_index(drop=True)
    pdf = pdf.assign(county=assign_county(pdf, counties))
    pdf = pdf.drop(columns=DROP_COLUMNS)
    return pdf.dropna(subset=["county"])


def main() -> None:
    download_counties()
    with dask_client() as client:
        print(f"Dask dashboard: {client.dashboard_link}")
        # Loaded once and shared by every partition instead of being copied into each task
        counties = dask.delayed(gpd.read_file(COUNTIES_ZIP))

        ddf = dd.read_csv(
            FIRES_CSV,
            dtype={
                "fire_name": "string",
                "county": "string",
                "fire_size_class": "string",
                "cont_dt": "string",
                "discovery_hour": "Int64",
            },
            parse_dates=["discovery_date"],
            blocksize="16MB",  # ~13 partitions, so every worker gets work
        )
        meta = ddf._meta.drop(columns=DROP_COLUMNS)
        clean = ddf.map_partitions(clean_partition, counties, meta=meta)

        clean.to_parquet(FIRES_CLEAN, write_index=False, overwrite=True)

        total = len(dd.read_parquet(FIRES_CLEAN))
    print(f"Clean dataset written to {FIRES_CLEAN} with {total:,} rows")


if __name__ == "__main__":
    main()
