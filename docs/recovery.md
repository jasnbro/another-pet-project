# Recovery runbook (ATLAS)

What to do when something breaks. For a normal deploy, rollback, or a
failed deploy, see `deploy/README.md`. This page covers the cases that page
doesn't.

## Where everything lives

| Thing | Where | Committed? |
|---|---|---|
| Code | This repo; running versions are tagged images (`mindless_meals:<sha>`, `gym_log:<sha>`) | Yes |
| App settings | Doppler projects `gym-log`, `mindless-meals` (`prd`), or `~/services/<app>/.env` for an app not moved yet (`deploy/README.md` → *Settings*) | No |
| Postgres superuser | `~/services/postgres/.env` | No |
| Backup settings and the decryption key | Doppler project `atlas-backups` (`prd`) | No |
| Offline copy of the decryption key | USB stick or printed copy, kept away from ATLAS | No |
| Nightly backups | `/mnt/backup-ssd/postgres/*.sql.gz.age` (14 days) | No |
| Pre-deploy backups | `~/backups/postgres/*.sql.gz` | No |

Settings kept in Doppler survive losing ATLAS. Any `.env` file still on
ATLAS isn't backed up anywhere: move it to Doppler (`deploy/README.md` →
*Settings*) or keep a copy in your password manager.

## Health checks

- Apps: `cd ~/services/<app> && docker compose ps` (`mindless_meals`, `gym_log`) should show `healthy`.
  The public site is https://meals.undercurrentlabs.dev/.
- Backups: `ls -l /mnt/backup-ssd/postgres/.last_success` should be dated within the last day.
  See `postgres/README.md#backups`.
- Deploy runner: **Settings → Actions → Runners** should show `Idle`.

## Data is wrong or lost, but ATLAS is fine

1. Pause deploys: **Actions → Mindless Meals → ⋯ → Disable workflow**.
2. Pick a backup. Use the newest nightly backup from before the problem. If
   the problem came from a migration, use the pre-deploy backup in
   `~/backups/postgres/`.
3. Restore it into a new database. Follow `postgres/README.md` →
   *Restoring for real*. Check the row counts and a few real rows.
4. Point the app at it by changing the database name in
   `~/services/<app>/.env`, then run `docker compose up -d`. Or
   rename the databases in `psql` while the app is stopped.
5. If the restored data predates a migration, roll the code back to match
   (see `deploy/README.md`). Then re-enable the workflow.

## The main disk died, or ATLAS was rebuilt

1. Reinstall the OS and Docker, create the `jasmine` user, and add it to the `docker` group.
2. Clone this repo to `~/services`. Recreate the `.env` files from your saved copies.
3. Start Postgres: `cd ~/services/postgres && docker compose up -d`.
4. Mount the backup SSD and install age and Doppler. Steps 1, 3 and 4 of
   *One-time setup* in `postgres/README.md`.
5. For each app database:
   - Create it empty, then restore its newest nightly backup with `restore.sh`.
   - If Doppler isn't set up yet, use the offline key:
     `BACKUP_AGE_IDENTITY_FILE=/path/to/atlas-backup.key ./restore.sh <file> <db>`.
6. Re-register the deploy runner (`deploy/README.md` → *Install the runner*).
   Then run **Actions → Mindless Meals → Run workflow → deploy** with `ref`
   blank. The image is rebuilt from `main`.
7. Start the Cloudflare tunnel (`~/services/cloudflared`). Confirm the site loads.
8. Put the cron job back (`postgres/README.md` → *Schedule it*).

## The backup SSD died

Production is unaffected. Replace the SSD and repeat step 4 of the
one-time setup with the new UUID. Then run the nightly command by hand.
Until it's replaced, the pre-deploy backups in `~/backups/postgres/` are
your only copies.

## ATLAS is gone (theft, fire)

There is no off-site copy yet (#27). Until there is, a loss of ATLAS and
the SSD together is unrecoverable. The code is safe on GitHub; the data is
not.
