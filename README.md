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

   This starts MongoDB and runs the system in four stages, one after the other:

   1. **Dask**: the Dask cluster starts and the `etl` service downloads, cleans and loads the
      fires into `mongodb://localhost:27017` (database `wildfires`, collection `fires`). Then
      it stops the Dask cluster.
   2. **Spark**: only then the Spark cluster starts (one master, two workers) and the `spark`
      service computes the spatial and temporal aggregations and saves them
      in new collections: `fires_by_grid`, `fires_hotspots`, `fires_by_hour`,
      `fires_by_weekday`, `fires_by_month`, `fires_by_year`, `fires_by_state` and
      `fires_by_cause`.
   3. **API**: the Flask API starts on http://localhost:5000.
   4. **Frontend**: the React dashboard starts on **http://localhost:3000**: the Spark grid
      and hotspots on a map, the temporal and spatial aggregations, and the `$near`,
      `$geoNear` and `$geoWithin` queries run from the map.

   Dashboards: Dask at http://localhost:8787 and Spark at http://localhost:8080. To run the
   Spark aggregations again: `docker compose run --rm spark`.

## API

All fire queries return GeoJSON FeatureCollections. `cause`, `state` and `year` are optional
filters on every fire query; `limit` defaults to 100 (max 1000).

| Endpoint | MongoDB query | Example |
|---|---|---|
| `GET /fires/near` | `$near`: fires within `radius_km` (default 10), nearest first | `/fires/near?lat=34.05&lon=-118.25&radius_km=5` |
| `POST /fires/within` | `$geoWithin`: fires inside a GeoJSON Polygon/MultiPolygon (or Feature) sent as the body | see below |
| `GET /fires/nearest` | `$geoNear` aggregation: nearest fires within `max_km` (default 50), with `distance_km` | `/fires/nearest?lat=37.77&lon=-122.42&year=2015` |
| `GET /stats/<name>` | Spark results: `grid`, `hotspots`, `hour`, `weekday`, `month`, `year`, `state`, `cause` | `/stats/hotspots?limit=10` |
| `GET /health` | MongoDB ping and number of fires | `/health` |

```bash
curl -X POST "localhost:5000/fires/within?limit=10&cause=Lightning" \
  -H "Content-Type: application/json" \
  -d '{"type": "Polygon", "coordinates": [[[-118.7, 33.7], [-117.9, 33.7], [-117.9, 34.4], [-118.7, 34.4], [-118.7, 33.7]]]}'
```

Invalid parameters return `400` with a JSON message.

## Frontend

React + TypeScript (Vite) in `frontend/`, managed with `pnpm`. In Docker, nginx serves the
build and forwards `/api/*` to the API, so the browser only talks to one origin.

To work on it without Docker (with the API running on port 5000):

```bash
cd frontend
pnpm install
pnpm dev     # http://localhost:3000, /api is forwarded to http://localhost:5000
pnpm test    # unit tests (vitest)
pnpm build   # type check + production build
```

The unit tests also run as a Docker build stage, which is what CI uses:
`docker build -f docker/frontend.Dockerfile --target test .`

## Team members

- Juan José Lopera Londoño ([@Loperaa-Juan](https://github.com/Loperaa-Juan))
- Antonio Patiño Mejía ([@Antonysw13](https://github.com/Antonysw13))
- Jairo Alberto Mejía Ramirez ([@Jairo-commit](https://github.com/Jairo-commit))
