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
| `.github/workflows/gym-log.yml` | The same for Gym Log (`APP=gym_log`); see below |
| `deploy/deploy-undercurrent.sh <sha>` | The Undercurrent site deploy (static, no database), run by `.github/workflows/undercurrent-checks.yml`; roll back with `APP=undercurrent deploy/rollback.sh` |

Script settings (environment variables, all optional): `APP` (default
`mindless_meals`), `SERVICE_DIR` (default `~/services/$APP`), `BACKUP_DIR` (default `~/backups/postgres`),
`HEALTH_TIMEOUT` (default 90s), `KEEP_IMAGES` (default 5).

## Gym Log

Gym Log (`gym_log/`) deploys with the same scripts: the **Gym Log**
workflow sets `APP=gym_log`, so everything above applies with
`~/services/gym_log`, image `gym_log:<sha>` and its own `gym_log`
database. Roll back from **Actions → Gym Log**, or by hand with
`APP=gym_log deploy/rollback.sh`.

A brand-new app's database has no Alembic revision yet. The deploy
accepts that only when the database has **no tables at all** and then
creates the schema from scratch; an untracked database that already has
tables is still refused (Mindless Meals' one-time adoption case).
One-time setup (database, `.env`, tunnel hostname, Cloudflare Access,
backups): `gym_log/README.md` → *Deploying*.

## Settings: Doppler, or a .env file

An app's settings (`DATABASE_URL`, the `IDENTITY_*` lines) come from one of:

- **Doppler**, project named after the app with dashes (`gym-log`,
  `mindless-meals`), config `prd`. This is used whenever
  `~/services/<app>/.env` doesn't exist. Deploys and rollbacks re-run
  themselves under `doppler run`, so nothing secret is kept in the service
  folder, and changing a setting means editing it in Doppler, not a file.
- **`~/services/<app>/.env`**, the old way. If the file exists, it wins
  and Doppler isn't consulted. You can move one app at a time.

`compose.yml` lists every setting an app reads. A deploy stops early if
`DATABASE_URL` is missing from both places, instead of quietly starting on
SQLite.

### Moving an app to Doppler (once per app, ~5 minutes)

On ATLAS, as `jasmine`, with the Doppler CLI installed and `doppler login`
done. This is the same login the nightly backups use.

1. `doppler projects create gym-log`. It comes with a `prd` config.
2. `doppler secrets upload --project gym-log --config prd ~/services/gym_log/.env`
3. Check the names (values stay hidden):
   `doppler secrets --project gym-log --config prd --only-names`
4. `mv ~/services/gym_log/.env ~/gym_log.env.bak`, then redeploy:
   **Actions → Gym Log → Run workflow → deploy**. The log should say
   `Settings: Doppler project 'gym-log' (prd)`.
5. Once it's healthy: `shred -u ~/gym_log.env.bak`. If anything went
   wrong, move the file back: the deploy changes nothing until its checks
   pass.

The settings every app shares (`IDENTITY_DATABASE_URL`, `IDENTITY_RP_ID`,
`IDENTITY_COOKIE_DOMAIN`) can live once in a Doppler project
`undercurrent-identity`. Each app's `prd` config then references them, e.g.
`IDENTITY_DATABASE_URL = ${undercurrent-identity.prd.IDENTITY_DATABASE_URL}`.
If your Doppler plan doesn't allow cross-project references, paste them
into each app instead.

### Day to day with Doppler

| I want to… | Do this |
|---|---|
| Change a setting | Edit it in Doppler, then **Run workflow → deploy**. The running container keeps the old value until then |
| Start or restart by hand | `cd ~/services/gym_log && doppler run -p gym-log -c prd -- docker compose up -d` (plain `restart` also works; it keeps the current values) |
| Run an admin command | `docker compose exec gym_log flask --app app identity …`. No Doppler step needed: it runs inside the running container |

If a deploy log shows a Doppler error (not logged in, unknown project),
nothing was changed. Fix the login or the project name and run it again.
Containers keep their settings in Docker's own root-only files under
`/var/lib/docker`, so a reboot needs no Doppler step.
