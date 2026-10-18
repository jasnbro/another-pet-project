# Automated deploys (ATLAS)

**What happens:** merge a PR into `main` → GitHub runs the tests → if they
pass, the runner on ATLAS deploys it. Usually live within a few minutes.
GitHub emails you if a deploy fails. Every run is in the repo's
**Actions → Mindless Meals** tab.

Each deploy:
1. Builds an image of that exact commit (`mindless_meals:<sha>`).
2. On Postgres: refuses to continue unless the database is tracked by
   Alembic, **backs it up**, then applies any new migrations.
3. Switches the app to the new image and waits for its health check.
4. If it isn't healthy, **switches back to the previous version** and fails.

It only touches Mindless Meals. `.env`, `./data` and other services are
never changed. The last few images are kept for instant rollback.

---

## One-time setup (~15 minutes)

### 1. GitHub settings (this is what makes the runner safe)
The repo is public, so these matter. In the repo's **Settings**:
- **General → Features → Pull requests → Collaborators only.** Strangers can
  still read the code but can't open PRs. Don't invite collaborators casually:
  anyone who can push to `main` can run code on ATLAS.
- **Actions → General → Fork pull request workflows → Require approval for
  all external contributors.** A backstop if the PR setting is ever changed.
- **Actions → General → Workflow permissions → Read repository contents.**

### 2. Install the runner on ATLAS
As `jasmine` (not root), who must be in the `docker` group
(`groups` shows it; if not: `sudo usermod -aG docker jasmine`, then log out
and back in):

1. GitHub repo → **Settings → Actions → Runners → New self-hosted runner →
   Linux**. Run the download and `./config.sh` commands it shows, in
   `~/actions-runner`.
2. When `config.sh` asks for **additional labels**, enter: `atlas`
3. Run it as a service so it survives reboots:
   ```
   cd ~/actions-runner
   sudo ./svc.sh install jasmine
   sudo ./svc.sh start
   ```
The runner shows as **Idle** under Settings → Actions → Runners when ready.

### 3. Check the database is tracked by Alembic
```
cd ~/services/mindless_meals
docker compose run --rm --no-deps mindless_meals alembic current
```
- Shows a revision like `a1b2c3d4 (head)` → you're ready.
- Shows nothing → do the one-time adoption in
  `mindless_meals/docs/database.md` → *Atlas deployment* first. Until then,
  deploys stop safely at step 2 and the current version keeps running.

### 4. First deploy
GitHub → **Actions → Mindless Meals → Run workflow** → action `deploy` →
**Run**. Watch it once. After that, merges deploy themselves.

> First deploy switches production from the old "code mounted from
> `./app`" setup to "code inside the image". `~/services/mindless_meals`
> then becomes deploy-managed: its `compose.yml` is replaced by the repo's,
> and `compose.override.yml` pins the running version. Don't `git pull` or
> edit there. The old `app/` folder is no longer used.

---

## Day to day

| I want to… | Do this |
|---|---|
| Ship a change | Merge the PR. That's it. |
| See what's running | `cd ~/services/mindless_meals && cat compose.override.yml` |
| See deploy history | `deploy/rollback.sh --list` (from the runner's checkout) or `cat ~/services/mindless_meals/.deploy/history` |
| Roll back | **Actions → Mindless Meals → Run workflow** → action `rollback`, ref blank (= previous version) or a commit SHA |
| Redeploy a specific commit | **Run workflow** → action `deploy`, ref = commit SHA |
| Pause automatic deploys | **Actions → Mindless Meals → ⋯ → Disable workflow** (re-enable the same way) |
| See app logs | `cd ~/services/mindless_meals && docker compose logs -f` |

Manual commands in `~/services/mindless_meals` (`docker compose logs`,
`restart`, `up -d`) still work and use the deployed version. **Don't use
`--build` there**; the code isn't in that folder anymore.

## When something goes wrong

- **Deploy failed, app still works:** it reverted itself. Read the failed
  run's log in Actions, fix, merge again.
- **Bad version is live (passed health check but is wrong):** roll back
  from Actions, as above. Takes seconds.
- **A migration broke data:** rollback restores *code only*, never the
  database. Every deploy backs up first, to `~/backups/postgres/`. Restore
  into a fresh database and check it before switching:
  `postgres/scripts/restore.sh` (see `mindless_meals/docs/database.md` →
  *Restoring a backup*). Roll the code back to match.
- **Runner offline:** Settings → Actions → Runners shows it. On ATLAS:
  `cd ~/actions-runner && sudo ./svc.sh status` / `sudo ./svc.sh start`.

## Files

| File | What it is |
|---|---|
| `.github/workflows/mindless-meals.yml` | Tests every PR; deploys `main` on the `atlas` runner; manual deploy/rollback |
| `deploy/deploy.sh <sha>` | The deploy (can also be run by hand from a checkout on ATLAS) |
| `deploy/rollback.sh [sha]` | Switch to an earlier image |
| `deploy/common.sh` | Shared helpers |
| `deploy/tests/` | Tests for the scripts, run in CI against a fake `docker` |

Settings (environment variables, all optional): `SERVICE_DIR` (default
`~/services/mindless_meals`), `BACKUP_DIR` (default `~/backups/postgres`),
`HEALTH_TIMEOUT` (default 90s), `KEEP_IMAGES` (default 5).
