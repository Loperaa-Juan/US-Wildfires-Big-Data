"""
This script reads and transforms the SQLite database loaded in the download.py script and convert it into a .CSV file
"""

import sqlite3
import pandas as pd

# Define the origin and destination paths
raw = "data/raw/FPA_FOD_20170508.sqlite"
destination = "data/processed/fires.csv"

# Create a list with the columns that we'll include in the .csv dataset
columns = ["FOD_ID", "FIRE_NAME", "FIRE_YEAR", "DISCOVERY_DATE", "DISCOVERY_TIME",
        "CONT_DATE", "CONT_TIME", "STAT_CAUSE_DESCR", "FIRE_SIZE", "FIRE_SIZE_CLASS",
        "OWNER_DESCR", "STATE", "COUNTY", "LATITUDE", "LONGITUDE"]

# Convert the datetime from julian to a normal datetime
def julian_to_iso(date, time):
    dt = pd.to_datetime(date - 2440587.5, unit="D")
    hhmm = pd.to_numeric(time, errors="coerce")
    return dt + pd.to_timedelta((hhmm // 100) * 60 + hhmm % 100, unit="min").fillna(pd.Timedelta(0))

# Connect to the sqlite database
con = sqlite3.connect(raw)

first = True
for chunk in pd.read_sql(f"SELECT {', '.join(columns)} FROM Fires", con, chunksize=100_000):
    # Apply the datetime conversion using the previous function
    chunk["discovery_dt"] = julian_to_iso(chunk.pop("DISCOVERY_DATE"), chunk.pop("DISCOVERY_TIME"))
    chunk["cont_dt"] = julian_to_iso(chunk.pop("CONT_DATE"), chunk.pop("CONT_TIME"))
    
    # Remove the records with null values in LATITUDE and LONGITUDE columns
    chunk = chunk.dropna(subset=["LATITUDE", "LONGITUDE"])
    chunk.columns = chunk.columns.str.lower()
    chunk.to_csv(destination, mode="w" if first else "a", header=first, index=False)
    first = False
