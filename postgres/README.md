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

Backups
--------
Every night, each database is dumped, gzip-compressed, **encrypted**, and
written to the external backup SSD. Backups older than 14 days are
deleted. A restore into a scratch database runs right afterwards to prove
the backup works. Every deploy also takes its own unencrypted backup before
running migrations (`deploy/deploy.sh`, kept in `~/backups/postgres`).

| Script (`postgres/scripts/`) | What it does |
|---|---|
| `nightly_backup.sh db ...` | The scheduled job. Refuses to run unless encryption and the SSD mount guard are both configured |
| `backup.sh [db ...]` | Does the dump. Encryption and the mount guard are optional, so the deploy can use it too |
| `restore_test.sh db` | Restores the newest backup into `<db>_restore_test`, compares every table's row count with the live database, then drops the scratch copy. The live database is only read |
| `restore.sh file db` | Restores a backup (`.sql.gz` or `.sql.gz.age`) into an existing, empty database |

Tests: `bash postgres/tests/test_backup.sh` (runs in CI).

### How the encryption works
Encryption uses [age](https://age-encryption.org) with a key pair:
- The **public key** (`age1...`) encrypts. It's all the nightly job
  needs, and it can't decrypt anything.
- The **private key** (`AGE-SECRET-KEY-...`) decrypts. It's needed only
  to restore, and it lives in two places: Doppler, and an **offline copy**
  outside Doppler (a USB stick or printed copy, stored somewhere other
  than with ATLAS). If both are lost, every backup is unreadable.

### One-time setup on ATLAS (~20 minutes)
1. **Install age and the Doppler CLI:** `sudo apt install age`, then
   follow Doppler's Linux install instructions and run `doppler login`.
2. **Make the key pair. Do this on your laptop, not on ATLAS:**
   `age-keygen -o atlas-backup.key`. It prints the public key. Save the
   file to the offline location, then delete the copy on the laptop.
3. **Create a Doppler project** `atlas-backups` with config `prd`, holding:
   - `BACKUP_AGE_RECIPIENT`: the public key
   - `BACKUP_AGE_IDENTITY`: the full contents of the private key file
   - `BACKUP_REQUIRE_MOUNT=/mnt/backup-ssd`
   - `BACKUP_DIR=/mnt/backup-ssd/postgres`
   - `DB_ROLE`: the Postgres superuser name (from `postgres/.env`)

   The commands below name the project and config explicitly, so no `doppler setup` is needed.
4. **Mount the SSD by UUID** so it can't swap device names:
   - **Find the right partition.** Run `lsblk -o NAME,SIZE,FSTYPE,TRAN,MODEL`.
     The external drive shows `usb` under `TRAN`. Ignore its small `EFI`
     partition. **Never** use the partition ATLAS runs from
     (`findmnt -n -o SOURCE /`).
   - Run `sudo blkid` and copy that partition's `UUID` and `TYPE`, then
     `sudo mkdir -p /mnt/backup-ssd`.
   - If it was auto-mounted (`findmnt /dev/sdXN` shows a path such as
     `/media/...`), run `sudo umount /dev/sdXN` first.
   - Add **one** of these lines to `/etc/fstab`, depending on `TYPE`:
     - **`ext4`:**
       ```
       UUID=<uuid>  /mnt/backup-ssd  ext4  defaults,nofail  0  2
       ```
     - **`exfat`** (ATLAS's current drive, `ArmorATD`, UUID `5D06-F845`).
       First run `sudo apt install exfatprogs`. exFAT can't store Linux
       owners, so the mount sets them. Use the numbers from `id -u jasmine`
       and `id -g jasmine`:
       ```
       UUID=5D06-F845  /mnt/backup-ssd  exfat  defaults,nofail,uid=1000,gid=1000,umask=077,x-systemd.device-timeout=10s  0  0
       ```
       `umask=077` keeps the backups private to `jasmine`. exFAT has no
       journal, so a power cut mid-write can damage it. The nightly restore
       test catches that the next morning. The upside: if ATLAS dies, macOS
       can read the drive, and `age` can decrypt the backups on a Mac.
   - Run `sudo systemctl daemon-reload && sudo mount -a && mountpoint /mnt/backup-ssd`.
   - Make the backup folder:
     - **ext4:** `sudo mkdir /mnt/backup-ssd/postgres && sudo chown jasmine: /mnt/backup-ssd/postgres`
     - **exfat:** `mkdir /mnt/backup-ssd/postgres` (the mount already makes `jasmine` the owner)
   - Check that `jasmine` can write there:
     `touch /mnt/backup-ssd/postgres/.write-test && rm /mnt/backup-ssd/postgres/.write-test && echo OK`.

   `nofail` lets ATLAS boot without the SSD attached. The backup then
   fails loudly instead of writing to the main disk.
5. **Schedule it** with `crontab -e` as `jasmine`. Backup at 2:15am, then
   the restore test straight after:
   ```
   MAILTO=""
   15 2 * * * cd ~/services/postgres/scripts && { doppler run -p atlas-backups -c prd -- ./nightly_backup.sh mindless_meals gym_log undercurrent_identity && doppler run -p atlas-backups -c prd -- ./restore_test.sh mindless_meals && doppler run -p atlas-backups -c prd -- ./restore_test.sh gym_log && doppler run -p atlas-backups -c prd -- ./restore_test.sh undercurrent_identity; } >> ~/backups/postgres-nightly.log 2>&1
   ```
   Add each new app's database to `nightly_backup.sh` and give it its own
   `restore_test.sh` (it takes one database at a time), e.g. `capacity` once it exists.
6. **Prove it once, by hand:**
   - Run the cron command yourself; it must end with `Restore test PASSED`.
   - Then run `sudo umount /mnt/backup-ssd`, run `doppler run -p atlas-backups -c prd -- ./nightly_backup.sh mindless_meals gym_log` again, and confirm it errors and nothing new appears in `~/` or `/mnt`.
   - Remount the SSD.

### Checking on it
- Last good backup: `ls -l /mnt/backup-ssd/postgres/.last_success`.
  Anything older than a day means the last run failed.
- What happened: `tail -50 ~/backups/postgres-nightly.log`.

### Restoring for real
Restore into a **new** database, check it, then point the app at it (or
swap names). Never restore over the live database.
```
docker exec -it postgres psql -U <POSTGRES_USER> -c "CREATE DATABASE mindless_meals_restored;"
doppler run -p atlas-backups -c prd -- ./restore.sh /mnt/backup-ssd/postgres/mindless_meals_<timestamp>.sql.gz.age mindless_meals_restored
```
Without Doppler (e.g. ATLAS rebuilt from scratch), use the offline key:
`BACKUP_AGE_IDENTITY_FILE=/media/usb/atlas-backup.key ./restore.sh ...`.
The full disaster-recovery runbook is in `docs/recovery.md`.

### Not covered yet
The SSD protects against main-disk failure, not against losing ATLAS itself
(theft, fire, a power surge). An off-site copy is tracked in #27.

Ad-hoc dumps (before a risky manual change):

    docker exec postgres pg_dump -U <POSTGRES_USER> mindless_meals > mindless_meals_backup.sql
    docker exec postgres pg_dumpall -U <POSTGRES_USER> > all_databases_backup.sql   # every database + roles

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
