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

   This starts MongoDB and runs the pipeline in two stages, one after the other:

   1. **Dask**: the Dask cluster starts and the `etl` service downloads, cleans and loads the
      fires into `mongodb://localhost:27017` (database `wildfires`, collection `fires`). Then
      it stops the Dask cluster.
   2. **Spark**: only then the Spark cluster starts (one master, two workers) and the `spark`
      service computes the spatial and temporal aggregations and saves them
      in new collections: `fires_by_grid`, `fires_hotspots`, `fires_by_hour`,
      `fires_by_weekday`, `fires_by_month`, `fires_by_year`, `fires_by_state` and
      `fires_by_cause`.

   Dashboards: Dask at http://localhost:8787 and Spark at http://localhost:8080. To run the
   Spark aggregations again: `docker compose run --rm spark`.
