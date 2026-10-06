"""
This script reads and transforms the SQLite database loaded in the download.py script and convert it into a .CSV file
"""

import sqlite3

import pandas as pd

from us_wildfires_big_data.config import FIRES_CSV, SQLITE_PATH

# Create a list with the columns that we'll include in the .csv dataset
columns = [
    "FOD_ID",
    "FIRE_NAME",
    "FIRE_YEAR",
    "DISCOVERY_DATE",
    "DISCOVERY_TIME",
    "CONT_DATE",
    "CONT_TIME",
    "STAT_CAUSE_DESCR",
    "FIRE_SIZE",
    "FIRE_SIZE_CLASS",
    "OWNER_DESCR",
    "STATE",
    "COUNTY",
    "LATITUDE",
    "LONGITUDE",
]


# Convert the date from julian to a normal date (time 00:00)
def julian_to_date(date):
    return pd.to_datetime(date - 2440587.5, unit="D")


# Hour (0-23) of an HHMM time; stays null when the time is unknown
def hhmm_to_hour(time):
    return (pd.to_numeric(time, errors="coerce") // 100).astype("Int64")


# Convert the datetime from julian to a normal datetime
def julian_to_iso(date, time):
    dt = pd.to_datetime(date - 2440587.5, unit="D")
    hhmm = pd.to_numeric(time, errors="coerce")
    return dt + pd.to_timedelta((hhmm // 100) * 60 + hhmm % 100, unit="min").fillna(
        pd.Timedelta(0)
    )


def main() -> None:
    # Connect to the sqlite database
    con = sqlite3.connect(SQLITE_PATH)
    FIRES_CSV.parent.mkdir(parents=True, exist_ok=True)

    first = True
    for chunk in pd.read_sql(
        f"SELECT {', '.join(columns)} FROM Fires", con, chunksize=100_000
    ):
        # 47% of the records have no DISCOVERY_TIME. Filling it with 00:00 would mix them with
        # the real midnight fires, so the date and the hour are kept apart and the hour stays null
        chunk["discovery_date"] = julian_to_date(chunk.pop("DISCOVERY_DATE"))
        chunk["discovery_hour"] = hhmm_to_hour(chunk.pop("DISCOVERY_TIME"))
        chunk["cont_dt"] = julian_to_iso(chunk.pop("CONT_DATE"), chunk.pop("CONT_TIME"))

        # Remove the records with null values in LATITUDE and LONGITUDE columns
        chunk = chunk.dropna(subset=["LATITUDE", "LONGITUDE"])
        chunk.columns = chunk.columns.str.lower()
        chunk.to_csv(FIRES_CSV, mode="w" if first else "a", header=first, index=False)
        first = False


if __name__ == "__main__":
    main()
