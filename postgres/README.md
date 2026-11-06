Postgres
========

Purpose
-------
Shared Postgres 17 database server for the small self-hosted apps in
`~/services`. Sized for personal/small-scale use (a handful of apps,
~20 users or less each) — the stock Postgres image with no special
tuning is more than enough at this scale and won't strain this
machine.

One Postgres **server**, many **databases** — each app gets its own
database inside this one server (see "Adding a database for a new
app" below), rather than every app running its own Postgres
container. Less memory used overall, and one place to back up.

There's no `Dockerfile` here on purpose: this service runs the
official `postgres:17` image unmodified, so there's nothing to build.

How it's wired up
------------------
- `compose.yml` — defines the one `postgres` container. Reads its
  superuser credentials from `.env` (see below).
- `.env` — **secrets, not committed to git** (see the repo's
  `.gitignore`). Holds `POSTGRES_USER`, `POSTGRES_PASSWORD`,
  `POSTGRES_DB`. Already created on this machine — you shouldn't need
  to touch it unless you're setting this service up fresh elsewhere.
- `.env.example` — a template showing the shape of `.env` without
  real secrets, so you (or future-you on a new machine) know what to
  fill in.
- `data/` — the actual database files, bind-mounted into the
  container. This is the real database — back it up (see below),
  don't delete it.
- **Networking:** this container publishes no port to the host or
  LAN. It's only reachable by other containers attached to the
  `postgres_default` Docker network — see "Connecting an app to
  Postgres" below. Nothing on your network can connect to port 5432
  directly anymore; only containers on this machine can.

Starting / stopping
--------------------
    cd ~/services/postgres
    docker compose up -d       # start (or apply changes to compose.yml/.env)
    docker compose down        # stop and remove the container (data/ is untouched)
    docker compose ps          # check status / health
    docker compose logs -f     # follow logs, Ctrl+C to stop watching

`docker compose down` does **not** delete your data — `data/` is a
plain folder on disk, not a Docker-managed volume, so it survives
container removal. There's nothing to be scared of running `down`
followed by `up -d` again.

Checking it's healthy
----------------------
    docker compose ps

Should show `healthy` once the container is up (it takes a few
seconds after start). If it's stuck on `starting` or shows
`unhealthy`, check `docker compose logs`.

Connecting an app to Postgres
------------------------------
Any other service on this machine that needs this database joins the
`postgres_default` network in its own `compose.yml`:

    services:
      your_app:
        # ...
        networks:
          - postgres_default

    networks:
      postgres_default:
        external: true

From inside that app's container, the database is reachable at host
`postgres`, port `5432` (Docker's built-in DNS resolves the container
name). A connection string looks like:

    postgresql://<user>:<password>@postgres:5432/<database_name>

`mindless_meals` already does this — see `~/services/mindless_meals/README.md`.

Adding a database for a new app
---------------------------------
Each app should get its own database (not share `mindless_meals`'s,
for example), so one app's data/mistakes stay isolated from another's:

    docker exec -it postgres psql -U madamada -d postgres \
      -c "CREATE DATABASE your_app_name OWNER madamada;"

Then point that app's `DATABASE_URL` at
`postgresql://madamada:<password>@postgres:5432/your_app_name`.

(This setup reuses the one existing superuser, `madamada`, for every
app's database rather than creating a separate role per app — simpler
to manage at this scale. If this ever needs tighter isolation between
apps, create a dedicated role with `CREATE ROLE` and `GRANT` it access
to only its own database.)

Poking around / running SQL by hand
-------------------------------------
    docker exec -it postgres psql -U madamada -d <database_name>

Useful psql commands once connected: `\l` (list databases), `\dt`
(list tables in the current database), `\d <table>` (describe a
table), `\q` (quit).

Backup and restore
--------------------
Back up one database:

    docker exec postgres pg_dump -U madamada mindless_meals > mindless_meals_backup.sql

Restore it (into an existing, empty database of the same name):

    cat mindless_meals_backup.sql | docker exec -i postgres psql -U madamada -d mindless_meals

Back up *everything* on the server (all databases + roles) in one file:

    docker exec postgres pg_dumpall -U madamada > all_databases_backup.sql

Those are fine for a one-off snapshot before a risky change. The
regular backups use the scripts in `scripts/`:

- `backup.sh <db>` — one gzip'd plain-SQL dump, timestamped, with
  14-day local retention.
- `restore.sh <file.sql.gz> <db>` — restores a dump into an existing,
  empty database.
- `nightly.sh` — runs `backup.sh` for every app database, then copies
  the dumps to the attached backup drive and to an encrypted Google
  Drive folder. Every step runs even if one fails; the log says which.

### Where the copies live (3-2-1)

1. `~/backups/postgres` on Atlas (14 days).
2. The plugged-in drive, `/mnt/backupdrive/postgres` (kept until you
   prune it). Protects against Atlas's main disk dying.
3. Google Drive, encrypted, via the `gdrive-crypt:` rclone remote (90
   days). The off-site copy: survives theft, fire or a dead Atlas.

### One-time setup

1. **Install rclone:** `sudo -v ; curl https://rclone.org/install.sh | sudo bash`
2. **Google Drive remote:** `rclone config` → new remote `gdrive`,
   type `drive`, blank client id/secret, scope `drive.file` (rclone
   only sees files it created). Answer `n` to auto config, run
   `rclone authorize "drive"` on a laptop with a browser, paste the
   token back.
3. **Encrypted remote:** `rclone config` → new remote `gdrive-crypt`,
   type `crypt`, remote `gdrive:atlas-backups`, standard filename
   encryption, directory names encrypted, generate both passwords.
   **Store both passwords in the password manager.** Without them the
   off-site backups can't be decrypted by anyone.
4. **Attached drive:** make sure it mounts at `/mnt/backupdrive` on
   boot (an `/etc/fstab` entry by UUID). `nightly.sh` skips it, with a
   warning, whenever it isn't mounted.
5. **Cron** (`crontab -e`; your user must be in the `docker` group):

        0 2 * * * /home/jasmine/services/postgres/scripts/nightly.sh >> /home/jasmine/backups/postgres/backup.log 2>&1

   `nightly.sh` loads `../.env` itself, so cron gets `POSTGRES_USER`.
6. **New app database?** Add it to `BACKUP_DATABASES` (an env var
   read by `nightly.sh`, default `mindless_meals`), e.g. in the cron
   line: `BACKUP_DATABASES="mindless_meals gym_log" /home/jasmine/...`.

### Checking it works

- After the first night: `tail -n 20 ~/backups/postgres/backup.log`
  should end with `Nightly backup OK`.
- `rclone ls gdrive-crypt:postgres` shows readable file names;
  `rclone ls gdrive:atlas-backups` shows scrambled ones (that's the
  encryption).
- **Test a restore from the off-site copy** at least once, and again
  every few months:

        rclone copy gdrive-crypt:postgres/<file>.sql.gz /tmp/restore-test/
        docker exec postgres createdb -U madamada restore_test
        DB_ROLE=madamada ./scripts/restore.sh /tmp/restore-test/<file>.sql.gz restore_test
        docker exec -it postgres psql -U madamada -d restore_test -c '\dt'
        docker exec postgres dropdb -U madamada restore_test

  Never restore over a real app database to test.

Changing the password
------------------------
Editing `POSTGRES_PASSWORD` in `.env` and restarting does **not**
change an existing database's password — those environment variables
only take effect the *first* time a data directory is initialized.
To actually change it:

    docker exec -it postgres psql -U madamada -d postgres \
      -c "ALTER ROLE madamada WITH PASSWORD 'new-password-here';"

Then update `.env` (and every app's `DATABASE_URL` that uses this
password) to match, and restart those apps.

Troubleshooting
------------------
- **`connection refused` from an app container** — Postgres isn't
  running, or that app isn't on the `postgres_default` network.
  Check `docker compose ps` here and `docker network inspect
  postgres_default` to see which containers are attached.
- **`role "..." does not exist`** — wrong username in the connection
  string; the only role that exists is whatever `POSTGRES_USER` was
  set to at first init (check `.env`).
- **`database "..." does not exist`** — the database hasn't been
  created yet; see "Adding a database for a new app" above.
