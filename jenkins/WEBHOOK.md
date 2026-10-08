# With the repository owner: webhook and branch protection

Two things only an admin of the repository (`Loperaa-Juan`) can set up on GitHub. Both build on
the Jenkins from [`JENKINS.md`](JENKINS.md), which must already be running and building.

| | What it adds |
|---|---|
| [1. Webhook](#1-webhook-through-ngrok) | GitHub tells Jenkins about every push and pull request as it happens, so builds start within seconds instead of at the next scan (up to 5 minutes later). |
| [2. Branch protection](#2-block-merging-when-the-build-fails) | GitHub refuses to merge a pull request whose Jenkins build is red. |

## 1. Webhook through ngrok

GitHub has to send the webhook to Jenkins, but Jenkins runs at `localhost`, which only exists on
this PC, and the router blocks connections that come from the internet. [ngrok](https://ngrok.com/)
gives Jenkins a public HTTPS address and forwards every request it receives, through a tunnel, to
`localhost:8090`. The scan works without it because there Jenkins makes the requests (outgoing),
which needs no public address.

1. Install ngrok, create a free account and add its token
   (`ngrok config add-authtoken <token>`, shown on the ngrok dashboard). Then, in a terminal you
   leave open:

   ```bash
   ngrok http 8090
   ```

   It shows a URL like `https://abc123.ngrok-free.app`. To get the same URL every time, claim the
   free static domain on the ngrok dashboard and run `ngrok http --url=<your-domain> 8090`.

2. In Jenkins, **Manage Jenkins → System → Jenkins URL**: the ngrok URL. The ✓/✗ that Jenkins
   posts on GitHub then link to an address teammates can open (while ngrok runs).

3. **The owner** adds the webhook on GitHub, in the repository's **Settings → Webhooks → Add webhook**:
   - **Payload URL**: `https://<ngrok-url>/github-webhook/` (the trailing `/` is required)
   - **Content type**: `application/json`
   - **Which events**: *Let me select individual events* → **Pushes** and **Pull requests**
     (uncheck the rest). *Pushes* starts the `main` build when something is merged into it;
     *Pull requests* starts a `PR-<number>` build when one is opened or updated.
   - **Active**: checked → **Add webhook**.

   GitHub sends a test ping; it should show a green ✓ under **Recent Deliveries**.

4. In the Jenkins job's **Configure → Scan Repository Triggers**, change the interval to
   *1 hour*. The webhook starts the builds now; the scan only catches what a missed webhook
   skipped (for example while the PC was off).

5. **Check it**: merge something into `main`. The `main` build starts within seconds, and
   **Recent Deliveries** shows the `push` event with a ✓.

Nothing changes in the `Jenkinsfile`: the job's GitHub source receives the webhook itself.

**After turning the PC on**, start ngrok again. With the free random URL, the owner has to update
the webhook's Payload URL and you the Jenkins URL every time; the static domain avoids it.
GitHub does not retry deliveries that failed while the PC was off: the hourly scan picks them up,
or click **Scan Repository Now**, or **Redeliver** them from **Recent Deliveries**.

## 2. Block merging when the build fails

Jenkins only reports the ✓/✗; GitHub is what stops the merge. Once a red build (a failing test,
a lint error or an outdated `uv.lock`) marks the pull request ✗, the merge button is disabled.

1. Open a pull request into `main` and wait until Jenkins posts its check on it, a ✓ or ✗ named
   **`continuous-integration/jenkins/pr-merge`**. GitHub only lists a check it has already seen,
   so this has to happen first.
2. **The owner**, in the repository's **Settings → Branches → Add branch protection rule**:
   - **Branch name pattern**: `main`
   - ✅ **Require a pull request before merging**
   - ✅ **Require status checks to pass before merging**, then search for
     `continuous-integration/jenkins/pr-merge` and add it.
   - ✅ **Require branches to be up to date before merging** (optional): a pull request that is
     behind `main` has to be updated, and rebuilt, before merging.
   - ✅ **Do not allow bypassing the above settings**, so admins cannot merge a red build either
     (leave it unchecked to keep an escape for when Jenkins is down).
   - **Create**.
3. **Check it**: on a branch, make a test fail and open a pull request. Its build stops at
   *Test*, the pull request shows ✗ and the merge button is disabled until a new commit makes the
   build green.

While this PC is off, pull requests wait on *Pending* and nobody can merge them, unless an admin
bypasses the rule.

## Troubleshooting

- **The webhook shows a red ✗ in Recent Deliveries**: ngrok is not running, the URL changed (the
  free random URL changes every time ngrok restarts), or the trailing `/` of `/github-webhook/`
  is missing. Open the delivery to see the response.
- **The webhook is ✓ but no build starts**: the job's Behaviours must include *Discover branches*
  and the filter `main PR-*` ([`JENKINS.md`](JENKINS.md), B2), and the push must be to `main` or
  to a branch with an open pull request.
- **The check does not show up in the branch protection search**: Jenkins has not reported it on
  any commit yet. Open a pull request, wait for its ✓/✗ and search again (2.1).
- **A pull request is stuck on *Pending* and cannot be merged**: Jenkins never reported, because
  this PC, the Jenkins container or ngrok is off. Start them and click **Scan Repository Now**;
  if that is not possible, an admin can merge by bypassing the rule.
- **"HTTP ERROR 403 No valid crumb was included in the request" in Jenkins**: you opened Jenkins
  through the ngrok URL and the session belongs to `localhost:8090`, or the other way around.
  Use one address; reload, log in again and save again.
