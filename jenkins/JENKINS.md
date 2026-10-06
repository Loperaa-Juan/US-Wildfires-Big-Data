# Continuous integration (Jenkins)

Every pull request into `main` is tested by Jenkins: it installs the dependencies, runs the linter
(`ruff`) and runs the tests (`pytest`). If any step fails, the build is marked red. Pushing to a
branch does **not** start a build; only opening a pull request (or adding commits to an open one)
does.

Right now Jenkins finds pull requests by **scanning** the repository (it asks GitHub every
5 minutes). Once the repository owner adds a webhook, builds can start right after a pull request
is opened; see [Later: webhook + ngrok](#later-webhook--ngrok).

## How it works

```
open PR into main ──► GitHub ◄── every 5 min: "new or updated PRs?" ── Jenkins on localhost:8080
                                                                              │
                                                        one job per pull request (PR-1, PR-2…)
                                                        runs the Jenkinsfile stages:
                                                        Install → Lint → Test → test report
```

1. Someone opens a pull request into `main` (or pushes a new commit to an open one).
2. Every 5 minutes Jenkins scans the repository for pull requests it has not built yet.
3. For each one, Jenkins creates a job named after the pull request (`PR-12`), checks out the pull
   request **merged with the current `main`** (what `main` would look like after merging), and
   runs the steps in the [`Jenkinsfile`](Jenkinsfile):
   - **Install**: `uv sync --locked` installs Python 3.13 and the exact versions in `uv.lock`.
   - **Lint**: `uv run ruff check .`
   - **Test**: `uv run pytest`, which writes a JUnit report that Jenkins shows on the build page.
4. When the pull request is merged or closed, Jenkins removes its job on the next scan.

| File | What it does |
|---|---|
| [`Jenkinsfile`](Jenkinsfile) | The pipeline stages. They only run for pull requests whose target is `main` (`when { changeRequest target: 'main' }`). |
| [`jenkins/Dockerfile`](jenkins/Dockerfile) | The official Jenkins image plus `uv`, the only tool the pipeline needs. Jenkins runs as its own container, apart from the project's `docker-compose.yml`, so running the ETL does not start Jenkins. |

### Why a Multibranch Pipeline job

A plain **Pipeline** job follows one fixed branch and has no idea what a pull request is. A
**Multibranch Pipeline** job with a **GitHub** source asks GitHub for the repository's branches and
pull requests and creates one job for each one it is told to discover. Here it is told to discover
**only pull requests**, so branches (including `main`) get no job and pushes to them build nothing.

### Things to keep in mind

- **One Jenkins serves the whole team.** The `Jenkinsfile` lives in the repository and Jenkins
  scans the repository, so a pull request from anyone is built. Teammates do not set up anything.
- **It only runs while this PC is on** and the Jenkins container is running. Pull requests opened
  while it is off are found by the next scan after it starts again.
- **Results are only visible in this Jenkins**, not on the pull request page in GitHub.
- **Use a GitHub token**, even though the repository is public. Scanning uses the GitHub API, which
  allows only 60 requests per hour without a token; a scan every 5 minutes runs out of that
  quickly. With a token the limit is 5,000 per hour. The token only needs to read public
  repositories, so it works even though the repository belongs to someone else (setup step 4).

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

**SCM** is *Source Control Management*: the system that stores the code's history (Git, SVN, …).
Jenkins supports several, so its settings say "SCM" instead of "Git".

The pipeline steps are read from the `Jenkinsfile` in the Git repository instead of being pasted
into a text box in Jenkins. That way the pipeline is versioned, reviewed in pull requests and
survives a Jenkins reinstall. It also means the `Jenkinsfile` must be pushed to GitHub: Jenkins
reads it from there, not from a local folder.

## Setup

1. **Build the image and start Jenkins**:

   ```bash
   docker build -t us-wildfires-jenkins jenkins/
   docker run -d --name jenkins --restart unless-stopped \
     -p 8080:8080 -v jenkins-home:/var/jenkins_home us-wildfires-jenkins
   ```

   The `jenkins-home` volume keeps jobs, plugins, users and build history when the container is
   stopped or recreated. Stop it with `docker stop jenkins` and start it again with
   `docker start jenkins`.

2. **Get the initial admin password**:

   ```bash
   docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
   ```

3. Open http://localhost:8080, paste the password, choose **Install suggested plugins** (they
   include Git, Pipeline, GitHub Branch Source and JUnit) and create your admin user.

4. **Create a GitHub token** (on your own GitHub account): **Settings → Developer settings →
   Personal access tokens → Fine-grained tokens → Generate new token**:
   - **Repository access**: *Public repositories* (read-only access to all public repositories).
   - **Permissions**: none.

   Copy the token; GitHub only shows it once.

5. **Create the job**: **New Item** → name `us-wildfires-big-data` → **Multibranch Pipeline** → OK.
   Then:
   - **Branch Sources** → **Add source** → **GitHub**.
     - **Credentials** → **Add** → **Jenkins**: kind *Username with password*, **Username**: your
       GitHub username, **Password**: the token. Select it.
     - **Repository HTTPS URL**: `https://github.com/Loperaa-Juan/US-Wildfires-Big-Data.git`
       and click **Validate**.
     - **Behaviours**:
       - **Delete** *Discover branches*. This is what stops pushes to branches from building.
       - Keep *Discover pull requests from origin* with strategy *Merging the pull request with
         the current target branch revision*.
       - Keep *Discover pull requests from forks* (strategy *Merging…*, trust *From users with
         Admin or Write permission*), so pull requests from teammates' forks are tested too. For
         forks without write access, Jenkins uses the `Jenkinsfile` from `main` instead of the
         one in the pull request, so a stranger cannot change what Jenkins runs.
   - **Build Configuration**: *by Jenkinsfile*, **Script Path**: `Jenkinsfile`.
   - **Scan Repository Triggers**: check **Periodically if not otherwise run**, **Interval**:
     *5 minutes*. Save.

6. Saving starts a first scan. Open **Scan Repository Log**: it lists the open pull requests it
   found. Under the job, the **Pull Requests** tab shows one job per pull request, each with a
   build. The build page shows the *Install*, *Lint* and *Test* stages and **Test Result**.

7. Open a test pull request into `main`. Within 5 minutes a `PR-<number>` job appears and builds.
   Push another commit to that pull request and it is built again on the next scan. Pushing to a
   branch without a pull request builds nothing.

## Later: webhook + ngrok

With a webhook, GitHub tells Jenkins as soon as a pull request is opened or updated, so builds
start within seconds instead of up to 5 minutes later. Adding a webhook needs **admin access** to
the repository, so the repository owner (`Loperaa-Juan`) has to do step 2.

### Why ngrok is needed for the webhook

With scanning, Jenkins makes the requests (outgoing), which works from any PC. A webhook is the
other way around: GitHub's servers send the request to Jenkins. Jenkins runs at
`localhost:8080`, which only exists on this machine, and the router blocks connections that come
from the internet, so GitHub cannot reach it. [ngrok](https://ngrok.com/) opens a public HTTPS
address (for example `https://abc123.ngrok-free.app`) and forwards every request it receives,
through a tunnel, to the local Jenkins. ngrok is not needed if Jenkins runs on a server with a
public address (a cloud VM, a company server).

### Steps

1. **Expose Jenkins with ngrok** (in a separate terminal, leave it running):

   ```bash
   ngrok http 8080
   ```

   Copy the `https://….ngrok-free.app` URL and set it in Jenkins under
   **Manage Jenkins → System → Jenkins URL**.

2. **The repository owner adds the webhook**: **Settings → Webhooks → Add webhook**:
   - **Payload URL**: `https://<your-ngrok-url>/github-webhook/` (the trailing `/` is required)
   - **Content type**: `application/json`
   - **Which events**: *Let me select individual events* → only **Pull requests**

   GitHub sends a test ping; it should show a green ✓ under **Recent Deliveries**.

3. Nothing changes in the `Jenkinsfile` or the job: the GitHub source receives the webhook
   itself. Keep the periodic scan as a safety net, but you can raise its interval (for example to
   *1 day*) to catch anything a missed webhook skipped.

4. Open a pull request into `main`. A build starts within a few seconds.

Keep in mind: the free ngrok URL changes every time ngrok restarts (the webhook then has to be
updated, or use ngrok's free static domain), and events sent while the PC or ngrok is off are
not retried by GitHub. The periodic scan picks them up, or click **Scan Repository Now**.

## Troubleshooting

- **No build after opening a pull request**: wait 5 minutes or click **Scan Repository Now**, then
  read the **Scan Repository Log**. Check that the pull request targets `main`.
- **The scan log mentions a rate limit**: the job has no credentials, or the token expired.
  Create a new token (setup step 4) and select it in the GitHub source.
- **Pushes to branches still start builds**: *Discover branches* is still in the **Behaviours**.
  Remove it and save; Jenkins deletes the branch jobs on the next scan.
- **A pull request into another branch shows a build with skipped stages**: expected, the
  `Jenkinsfile` only runs the stages for pull requests into `main`.
- **The webhook shows a red ✗ in Recent Deliveries**: ngrok is not running, the URL is wrong,
  or the trailing `/` of `/github-webhook/` is missing. Open the delivery to see the response.
- **"HTTP ERROR 403 No valid crumb was included in the request" when saving**: the crumb is
  Jenkins' anti-forgery token, tied to your login session, and that session ended (the container
  restarted while the page was open, the session timed out, or the page was opened at a different
  address such as `127.0.0.1` or the ngrok URL). Nothing was saved: reload the configure page,
  log in again if asked, enter the settings again and save. Always use `http://localhost:8080`.
- **A stage fails**: open the build → **Console Output**. Run the same command locally
  (`uv run ruff check .` or `uv run pytest`) to reproduce it.
