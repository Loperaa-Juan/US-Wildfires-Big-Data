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

## How to run it with Jenkins

Jenkins runs locally in a container and uses this PC's Docker to test, build and deploy the
system. Every pull request into `main` is tested; every change that reaches `main` is tested,
built, checked through the API and deployed on http://localhost:5000. The full guide, with the
reasons behind each step and troubleshooting, is in [`jenkins/JENKINS.md`](jenkins/JENKINS.md).

1. Stop the stack if you started it by hand (the deployed stack uses the same ports):

   ```bash
   docker compose down
   ```

2. Create Jenkins' data folder. It must have the same path on the PC and inside the container:

   ```bash
   sudo mkdir -p /var/jenkins_home
   sudo chown -R 1000:1000 /var/jenkins_home
   ```

3. Build the Jenkins image (Jenkins plus `uv`, the Docker CLI and `jq`) and start it with access
   to the PC's Docker:

   ```bash
   docker build -t us-wildfires-jenkins jenkins/
   docker run -d --name jenkins --restart unless-stopped \
     -p 8090:8080 \
     -v /var/jenkins_home:/var/jenkins_home \
     -v /var/run/docker.sock:/var/run/docker.sock \
     --group-add "$(stat -c %g /var/run/docker.sock)" \
     us-wildfires-jenkins
   ```

   Check that Jenkins can use Docker with `docker exec jenkins docker ps`.

4. Get the admin password, open http://localhost:8090, paste it, choose **Install suggested
   plugins** and create your admin user:

   ```bash
   docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
   ```

   Then set **Manage Jenkins → System → Jenkins URL** to `http://localhost:8090/`.

5. Add the credentials:
   - **GitHub**: a classic personal access token with the `repo:status` scope, from an account
     with write access to the repository.
   - **Kaggle**: in **Manage Jenkins → Credentials → System → Global credentials → Add
     Credentials**, kind *Username with password*, with the Kaggle `username` and `key` and the
     ID `kaggle` (exactly this).

6. Create the job: **New Item** → `us-wildfires-big-data` → **Multibranch Pipeline**.
   - **Branch Sources → GitHub**: the GitHub credential and
     `https://github.com/Loperaa-Juan/US-Wildfires-Big-Data.git`.
   - **Behaviours**: *Discover branches* (all branches), *Discover pull requests from origin*
     and *from forks* (merging with the target branch), and *Filter by name (with wildcards)*
     including `main PR-*`.
   - **Build Configuration**: *by Jenkinsfile*, script path `Jenkinsfile`.
   - **Scan Repository Triggers**: periodically, every *5 minutes*.

7. Check it. Open a pull request into `main`: within 5 minutes (or with **Scan Repository Now**)
   its `PR-<number>` job runs *Install → Lint → Test* and GitHub shows ✓ or ✗. Merge it: the
   `main` job also builds the images, starts a staging stack, runs the API tests and deploys.
   When it is green:

   ```bash
   curl localhost:5000/health
   docker compose -p wildfires ps
   ```

   If any test fails, nothing is deployed and the previous version keeps running.

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
