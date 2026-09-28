"""
This file downloads our dataset from Kaggle using kagglehub. For this project, we'll use the "1.88 Million US Wildfires" dataset.

NOTES:
- The dataset contains a spatial database of wildfires that occurred in the United States from 1992 to 2015.
- In this case, kaggle downloads the data in a sqlite database format. For this project, we need to transform it into a .CSV format
"""

from pathlib import Path

import kagglehub

# Define the specific route to store the raw data
ROOT = Path(__file__).resolve().parent.parent
RAW_DATA = ROOT / "data" / "raw"

# Download latest version of the data
path = kagglehub.dataset_download(
    "rtatman/188-million-us-wildfires", output_dir=RAW_DATA
)

print("Path to dataset files:", path)
