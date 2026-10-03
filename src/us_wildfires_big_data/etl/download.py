"""
This file downloads our dataset from Kaggle using kagglehub. For this project, we'll use the "1.88 Million US Wildfires" dataset.

NOTES:
- The dataset contains a spatial database of wildfires that occurred in the United States from 1992 to 2015.
- In this case, kaggle downloads the data in a sqlite database format. For this project, we need to transform it into a .CSV format
"""

import shutil
from pathlib import Path

import kagglehub

from us_wildfires_big_data.config import KAGGLE_DATASET, RAW_DATA, SQLITE_PATH


def main() -> None:
    if SQLITE_PATH.exists():
        print("Dataset already present at:", SQLITE_PATH)
        return

    path = Path(kagglehub.dataset_download(KAGGLE_DATASET))
    print("Path to dataset files:", path)

    # Copy the sqlite database into data/raw/
    source = next(path.rglob("*.sqlite"))
    RAW_DATA.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, SQLITE_PATH)
    print("Dataset copied to:", SQLITE_PATH)


if __name__ == "__main__":
    main()
