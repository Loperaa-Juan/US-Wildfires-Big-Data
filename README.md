# US Wildfires Big Data

Ingestion pipeline for the [1.88 Million US Wildfires](https://www.kaggle.com/datasets/rtatman/188-million-us-wildfires)
dataset: 1.88 million wildfires reported in the United States between 1992 and 2015. The data
is downloaded from Kaggle, cleaned with Dask and loaded into MongoDB as GeoJSON with a
`2dsphere` index, so it can be queried by location.

## How to run it

1. Install [Docker](https://docs.docker.com/get-docker/) and get a
   [Kaggle API token](https://www.kaggle.com/settings).

2. Clone the repository:

   ```bash
   git clone https://github.com/Loperaa-Juan/US-Wildfires-Big-Data.git
   cd US-Wildfires-Big-Data
   ```

3. Create the `.env` file and fill in `KAGGLE_USERNAME` and `KAGGLE_KEY`:

   ```bash
   cp .env.example .env
   ```

4. Start the system:

   ```bash
   docker compose up --build
   ```

   This starts MongoDB and the Dask cluster and runs the whole pipeline. When it finishes, the
   data is in `mongodb://localhost:27017` (database `wildfires`, collection `fires`).
