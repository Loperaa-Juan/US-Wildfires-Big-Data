# CI/CD with Jenkins

Jenkins tests every pull request into `main`. Every change that reaches `main` (a merged pull
request or a push) is tested, built into Docker images, started, checked through the API and
deployed.

| Event | Job | Stages |
|---|---|---|
| Pull request into `main` (opened, or new commits) | `PR-<number>` | Install → Lint → Test |
| Change that reaches `main` | `main` | Install → Lint → Test → Build images → Start services → API tests → Deploy |

Stages run in order and the build stops at the first failure. **If any test fails, nothing is
deployed.** Pushes to other branches build nothing.

Jenkins finds new pull requests and changes on `main` by **scanning** the repository every
5 minutes. A GitHub webhook can make builds start instantly; it needs the repository owner and is
set up separately in [`WEBHOOK.md`](WEBHOOK.md).

## How it works

```
 PR opened / merged into main
            │
            ▼
         GitHub ◄── every 5 min: "anything new?" ── Jenkins (container on this PC, port 8090)
            ▲                                             │
            └──────── ✓ / ✗ on the commit ────────────────┤  one job per pull request + main
                                                          │
                ┌─────────────────────────────────────────┴───────────────────────────┐
                │ every build                                                         │ main only
                ▼                                                                     ▼
   Install: uv sync --locked                          Build images: docker compose build
   Lint:    uv run ruff check .                       Start services: staging copy of the stack,
   Test:    uv run pytest → test report                 waits until the API is healthy
                                                      API tests: curl + jq on the endpoints
                                                      Deploy: stop staging, start/update the
                                                        deployed stack (API on localhost:5000)
```

1. Someone opens a pull request into `main`, adds commits to one, or merges one.
2. Within 5 minutes Jenkins' scan finds it (**Scan Repository Now** forces it).
3. Jenkins checks out the code and runs the [`Jenkinsfile`](../Jenkinsfile). A pull request is
   tested **merged with the current `main`**, so the result is what `main` would look like after
   merging.
4. Jenkins posts the result on GitHub as a ✓ or ✗ on the commit.

### Where is it deployed?

**On this PC.** There is no AWS or any other cloud involved. "Deploy" here means: run the
system's containers (MongoDB, Dask, Spark, API) on the same machine Jenkins runs on, through
this PC's Docker. After a green build of `main`, the deployed system is at
http://localhost:5000, and it keeps running until it is replaced by the next deploy.

How Jenkins can do that from inside a container: the Jenkins image has the Docker command line
but no Docker of its own. The PC's Docker socket (`/var/run/docker.sock`) is mounted into the
Jenkins container, so every `docker compose ...` in the pipeline is executed by the PC's Docker,
and the containers it starts run next to Jenkins, not inside it.

```
 this PC
 ├── Docker
 │   ├── jenkins                        ← runs the pipeline, sends docker commands to ↓
 │   ├── wildfires-staging-*  (during a build: started for the API tests, then removed)
 │   └── wildfires-*          (the deployed system: API on :5000, MongoDB on :27017, …)
 └── /var/run/docker.sock  ← shared with the jenkins container
```

In a company, the same pipeline would usually end differently: *Build images* pushes the images
to a registry (Docker Hub, AWS ECR…) and *Deploy* tells a server or a cloud service (an AWS EC2
machine, ECS, Kubernetes…) to run the new images. The stages and the rule "no deploy if a test
fails" are the same; only the target machine changes. Here the target is this PC.

### Staging and deployed stack

The pipeline starts the system twice from the same images, as two Docker Compose projects:

| | Compose project | Ports on this PC | Purpose |
|---|---|---|---|
| Staging | `wildfires-staging` | none ([`docker-compose.staging.yml`](docker-compose.staging.yml) removes them) | Started in every build of `main` to run the API tests against, then removed. Jenkins joins its network and calls `http://api:5000`. |
| Deployed | `wildfires` | the usual ones: API `5000`, MongoDB `27017`, Spark UI `8080`, Dask `8786`/`8787` | Only updated when every test passed. Stays up. |

Each project keeps its own MongoDB volume, so after the first build the ETL finds the fires
already loaded and skips the load. Both read the dataset from the build's `data/` folder, so
the Kaggle download and the Dask cleaning only happen once.

### Files

| File | What it does |
|---|---|
| [`Jenkinsfile`](../Jenkinsfile) | The pipeline: the stages above and when each one runs. |
| [`jenkins/Dockerfile`](Dockerfile) | The Jenkins image: Jenkins plus `uv`, the Docker CLI (with compose and buildx) and `jq`. |
| [`jenkins/docker-compose.staging.yml`](docker-compose.staging.yml) | Turns [`docker-compose.yml`](../docker-compose.yml) into the staging stack (no published ports). |
| [`jenkins/PIPELINE-FLOW.md`](PIPELINE-FLOW.md) | Why a pull request only runs CI and a merge runs the full pipeline: the job settings and the `when` conditions. |
| [`jenkins/api-tests.sh`](api-tests.sh) | The API tests: `curl` to `/health`, `/fires/near`, `POST /fires/within`, `/fires/nearest`, `/stats/hotspots` and an invalid request, checking each JSON response with `jq`. |
| [`tests/`](../tests/README.md) | The unit tests run by the *Test* stage, and how to add one. |

### What the course asks, and where it is

| Requirement | Where |
|---|---|
| Merging into `main` triggers Jenkins | The job discovers `main` (B2); the scan finds the merge. The webhook ([`WEBHOOK.md`](WEBHOOK.md)) makes it instant. |
| Tests on pull requests; tests and deploy on `main` | `Jenkinsfile`: stage `CI` (pull requests and `main`), stage `CD` with `when { branch 'main' }` |
| Build the images | Stage *Build images*: `docker compose build` |
| Docker inside Jenkins | `jenkins/Dockerfile` (Docker CLI) + `/var/run/docker.sock` mounted (A3) |
| Start the services, wait until the API is healthy | Stage *Start services*: `docker compose up -d --wait` |
| Basic tests against the API | Stage *API tests*: `jenkins/api-tests.sh` |
| No deploy if a test fails | *Deploy* is the last stage; any failure before it stops the build |
| Kaggle token as a Jenkins credential | Credential `kaggle` (B3), used with `withCredentials(...)` as `KAGGLE_USERNAME`/`KAGGLE_KEY` |

### Things to keep in mind

- **One Jenkins serves the whole team.** Changes from anyone are built. Teammates set up nothing.
- **It only runs while this PC is on.** The deployed system also lives on this PC, so it is only
  reachable from here (http://localhost:5000).
- **Teammates see the ✓/✗ on GitHub**, but its *Details* link points to this Jenkins, which only
  opens on this PC.

## Why there is no Maven

Most Jenkins tutorials use Maven because their example app is written in Java, and Maven is the
tool that builds and tests Java code. Jenkins does not need Maven: a pipeline stage just runs
shell commands. This project is Python, and `uv` does the job Maven does for Java:

| Job | Java project | This project |
|---|---|---|
| Declare dependencies | `pom.xml` | `pyproject.toml` |
| Lock exact versions | versions in `pom.xml` | `uv.lock` |
| Install dependencies | `mvn install` | `uv sync --locked` |
| Run the tests | `mvn test` (JUnit) | `uv run pytest` |

Jenkins itself is written in Java, but the Java it needs to run is already in the Jenkins image.

## What "SCM" means

**SCM** is *Source Control Management*: the system that stores the code's history (Git, SVN…).
The job reads the pipeline from the `Jenkinsfile` in the repository instead of a text box in
Jenkins, so the pipeline is versioned and reviewed in pull requests like the code. It also means
a change to the `Jenkinsfile` must be pushed to GitHub for Jenkins to see it.

## Setup

Everything here can be done without the repository owner. Commands run from the root of your
clone of the repository.

### A. Run Jenkins with access to Docker

Two changes from a plain Jenkins:

- **Port 8090 instead of 8080**: the deployed stack uses 8080 for the Spark UI.
- **Jenkins' data in the folder `/var/jenkins_home` on this PC, at the same path inside the
  container**, instead of a Docker volume. `docker-compose.yml` mounts `./data` into the
  containers, and that path is resolved by the PC's Docker, not inside Jenkins. The build's
  folder (`/var/jenkins_home/workspace/...`) must therefore exist at the same path on the PC.

1. **If you already run Jenkins** (from the `jenkins-home` volume), stop and remove the container
   (its data stays in the volume):

   ```bash
   docker stop jenkins && docker rm jenkins
   ```

2. **Create the folder**, owned by the `jenkins` user of the image (UID 1000). If you already ran
   Jenkins, copy its data in, so jobs, credentials and users are kept:

   ```bash
   sudo mkdir -p /var/jenkins_home
   # only if you already ran Jenkins:
   sudo cp -a /var/lib/docker/volumes/jenkins-home/_data/. /var/jenkins_home/
   sudo chown -R 1000:1000 /var/jenkins_home
   ```

3. **Build the image and start Jenkins** with the Docker socket:

   ```bash
   docker build -t us-wildfires-jenkins jenkins/
   docker run -d --name jenkins --restart unless-stopped \
     -p 8090:8080 \
     -v /var/jenkins_home:/var/jenkins_home \
     -v /var/run/docker.sock:/var/run/docker.sock \
     --group-add "$(stat -c %g /var/run/docker.sock)" \
     us-wildfires-jenkins
   ```

   - `-p 8090:8080`: Jenkins at http://localhost:8090.
   - `-v /var/jenkins_home:/var/jenkins_home`: same path on the PC and inside the container.
   - `-v /var/run/docker.sock:...`: the Docker CLI inside Jenkins talks to the PC's Docker.
   - `--group-add ...`: adds the `jenkins` user to the group that owns the socket, so it is
     allowed to use it.

   Docker starts it again when the PC boots. To update the image later, run `docker build` again,
   then `docker stop jenkins && docker rm jenkins` and the same `docker run`.

4. **Check that Jenkins can use Docker** (it lists this PC's containers):

   ```bash
   docker exec jenkins docker ps
   ```

5. **First time only** (no data copied in step 2): get the admin password with
   `docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword`, open
   http://localhost:8090, paste it, choose **Install suggested plugins** and create your admin
   user. Otherwise log in with your usual user.

6. In **Manage Jenkins → System → Jenkins URL**: `http://localhost:8090/`. The ✓/✗ on GitHub
   link to this address.

7. **Stop the stack if you run it by hand** from your clone (`docker compose up`). The deployed
   stack uses the same ports and cannot start while it is up:

   ```bash
   docker compose down
   ```

   From now on the deployed system is the one at http://localhost:5000. Stop it with
   `docker compose -p wildfires down` when you want to run your own copy.

When everything works, the old volume can be deleted with `docker volume rm jenkins-home`.

### B. Configure Jenkins

1. **GitHub token** (on your own GitHub account, which must have write access to the
   repository): **Settings → Developer settings → Personal access tokens → Tokens (classic) →
   Generate new token (classic)**, scope **`repo:status`** only. Jenkins needs it for two things:
   - **Posting the ✓/✗ on each commit.** Writing a commit status needs `repo:status`; a
     read-only token lets Jenkins build but every ✓/✗ fails silently (the build log shows
     *Could not update commit status*). A fine-grained token cannot be used here: it only
     reaches repositories owned by the account that creates it, and this one belongs to
     `Loperaa-Juan`.
   - **Scanning.** The scans use the GitHub API, which allows only 60 requests per hour without
     a token (5,000 with one).

2. **The job.** **New Item** → name `us-wildfires-big-data` → **Multibranch Pipeline** → OK (if it
   already exists, open **Configure** instead). Then:
   - **Branch Sources → Add source → GitHub**:
     - **Credentials → Add → Jenkins**: kind *Username with password*, **Username**: your GitHub
       username, **Password**: the token. Select it.
     - **Repository HTTPS URL**: `https://github.com/Loperaa-Juan/US-Wildfires-Big-Data.git`,
       then **Validate**.
     - **Behaviours**:
       - *Discover branches*, strategy *All branches*.
       - *Discover pull requests from origin*, strategy *Merging the pull request with the
         current target branch revision*.
       - *Discover pull requests from forks*, same strategy, trust *From users with Admin or
         Write permission* (for forks of anyone else, Jenkins runs the `Jenkinsfile` from `main`,
         so a stranger cannot change what Jenkins runs).
       - **Add → Filter by name (with wildcards)**: **Include** `main PR-*`, **Exclude** empty.
         Pull requests are named `PR-1`, `PR-2`…, so this keeps `main` and every pull request,
         and no other branch gets a job.
   - **Build Configuration**: *by Jenkinsfile*, **Script Path**: `Jenkinsfile`.
   - **Scan Repository Triggers**: **Periodically if not otherwise run**, *5 minutes*.

   Save. The scan log lists `main` and the open pull requests, and the job shows a **Branches**
   tab (`main`) next to **Pull Requests**. Delete any other job you created while trying things
   (for example `us-wildfires-big-data2`), so only one job builds each change.

3. **Kaggle credential.** Get your token at [kaggle.com → Settings → API](https://www.kaggle.com/settings)
   (*Create New Token* downloads `kaggle.json` with `username` and `key`). Then in
   **Manage Jenkins → Credentials → System → Global credentials (unrestricted) → Add Credentials**:
   - **Kind**: *Username with password*
   - **Username**: the Kaggle `username`
   - **Password**: the Kaggle `key`
   - **ID**: `kaggle` (exactly this: the `Jenkinsfile` looks it up by this ID)
   - **Description**: `Kaggle API token`

   Jenkins stores it encrypted and the pipeline gets it only inside `withCredentials(...)`, as
   the variables `KAGGLE_USERNAME` and `KAGGLE_KEY` that `docker-compose.yml` passes to the ETL.
   If it appears in the console output, Jenkins replaces it with `****`.

4. **Optional: skip the Kaggle download in the first build.** If your clone already has the
   dataset in `data/` (from running the system by hand), copy it into the folder of the `main`
   build before it runs. The ETL finds the files and skips the download, the transform and the
   cleaning:

   ```bash
   sudo mkdir -p /var/jenkins_home/workspace/us-wildfires-big-data_main
   sudo cp -a data /var/jenkins_home/workspace/us-wildfires-big-data_main/
   sudo chown -R 1000:1000 /var/jenkins_home/workspace/us-wildfires-big-data_main
   ```

   The Kaggle credential is still used whenever the files are missing.

### C. Check it end to end

The `CD` stages only run once this `Jenkinsfile` is on `main`, so the first full run is the merge
of the pull request that adds it.

1. **Pull request: tests only.** Push the branch and open (or update) its pull request into
   `main`. Within 5 minutes (or with **Scan Repository Now**) its `PR-<number>` job builds
   *Install*, *Lint* and *Test*; the `CD` stages show as skipped. The pull request shows the ✓.

2. **Merge: the whole pipeline.** Merge it. Within 5 minutes the `main` job builds every stage.
   The first build of `main` takes the longest: the ETL loads the fires into MongoDB and Spark
   runs the aggregations, once for staging and once for the deploy (plus the Kaggle download and
   the cleaning if you skipped B4). Later builds skip the download, the cleaning and the load.
   When it is green, the deployed system answers on this PC:

   ```bash
   curl localhost:5000/health
   docker compose -p wildfires ps
   ```

3. **A failing test blocks the deploy.** On a branch, make a test fail (for example change an
   expected value in `tests/test_transform.py`), open a pull request and merge it. The `main`
   build stops at *Test*, the following stages show as skipped, and the deployed system keeps
   the previous version (`docker compose -p wildfires ps` shows the containers' age unchanged).
   Revert the change with another pull request.

## Day to day

- **Adding tests**: see [`tests/README.md`](../tests/README.md). New API checks go in
  [`api-tests.sh`](api-tests.sh) as one more `check` line.
- **After turning the PC on**: Docker starts Jenkins and the deployed system by themselves.
  Changes made while the PC was off are found by the next scan.
- **The deployed system**: `docker compose -p wildfires ps`, `docker compose -p wildfires logs api`.

## Troubleshooting

- **No build after a pull request or a merge**: click **Scan Repository Now** and read the
  **Scan Repository Log**. Check that the pull request targets `main` and that the Behaviours
  include *Discover branches* and the filter `main PR-*` (B2).
- **Every branch gets a job**: the *Filter by name (with wildcards)* behaviour is missing (B2).
- **The build runs but no ✓/✗ appears on GitHub** (the build log shows *Could not update commit
  status*): the token cannot write commit statuses. Create a classic token with `repo:status`
  (B1), from an account with write access to the repository, and select it.
- **The scan log mentions a rate limit**: the GitHub source has no credentials, or the token
  expired. Create a new token (B1) and select it.
- **`permission denied while trying to connect to the Docker daemon socket`**: Jenkins was
  started without `--group-add` or without the socket mount. Recreate the container (A3).
- **The ETL fails with `Permission denied` on `/app/data`, or finds no data**: Jenkins' folder
  is not at the same path on the PC (`-v /var/jenkins_home:/var/jenkins_home`, A2–A3).
- **`Could not find credentials entry with ID 'kaggle'`**: the credential's ID is not exactly
  `kaggle` (B3).
- **Deploy fails with `port is already allocated`**: something else uses one of the stack's
  ports, usually the stack started by hand from your clone (A7) or an old Jenkins on 8080.
  `docker ps` shows who has it.
- **The build waits a long time at *Start services***: the ETL and Spark are running. Follow them
  with `docker compose -p wildfires-staging logs -f etl spark`. If one fails, the build fails and
  prints the last log lines of every staging container.
- **"HTTP ERROR 403 No valid crumb was included in the request" when saving**: the login session
  ended (Jenkins restarted while the page was open, or the page was opened at another address).
  Nothing was saved: reload the page, log in again and save again.
- **A CI stage fails**: open the build → **Console Output**, and run the same command locally
  (`uv sync --locked`, `uv run ruff check .` or `uv run pytest`) to reproduce it.
- **Install fails with `The lockfile at uv.lock needs to be updated`**: someone changed the
  dependencies in `pyproject.toml` without updating `uv.lock`. Run `uv lock` and commit
  `uv.lock`. Add dependencies with `uv add <package>` to avoid it.
