# US WILDFIRE BIG DATA

## Getting started

Requirements: [uv](https://docs.astral.sh/uv/getting-started/installation/).

Run these commands from the repository root:

1. Create the virtual environment and install the dependencies from `uv.lock`
   (uv downloads Python 3.13 automatically if it's missing):

   ```bash
   uv sync
   ```

2. Download the raw dataset from Kaggle into `data/raw/`:

   ```bash
   uv run scripts/download.py
   ```

3. Generate the cleaned CSV at `data/processed/fires.csv`:

   ```bash
   uv run scripts/transform.py
   ```
