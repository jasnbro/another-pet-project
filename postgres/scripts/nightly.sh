#!/usr/bin/env bash
# Nightly backup for the shared Postgres server on Atlas: dumps each app
# database with backup.sh, then copies the dumps to two other places:
#   1. a locally attached drive (protects against Atlas's main disk dying)
#   2. an encrypted rclone remote, e.g. Google Drive (off-site copy)
# See postgres/README.md#backup-and-restore for setup and restore testing.
#
# Usage (normally from cron, see README):
#   ./nightly.sh
#
# Configuration (environment variables, all optional):
#   BACKUP_DATABASES     Space-separated databases to dump
#                         (default: "mindless_meals")
#   BACKUP_DIR           Where backup.sh writes dumps
#                         (default: $HOME/backups/postgres)
#   LOCAL_COPY_MOUNT     Mount point of the attached backup drive
#                         (default: /mnt/backupdrive). Skipped with a warning
#                         if it isn't mounted, so dumps never land on Atlas's
#                         own disk by mistake.
#   OFFSITE_REMOTE       rclone remote + path for the encrypted copy
#                         (default: gdrive-crypt:postgres). Set to "" to skip.
#   OFFSITE_RETENTION    Delete off-site dumps older than this (rclone age,
#                         default: 90d). Local retention is backup.sh's
#                         RETENTION_DAYS.
#
# Exits non-zero if any step failed, after attempting every step, so one
# broken copy target never stops the others.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Cron runs with an almost empty environment. Load POSTGRES_USER (and the
# rest of the server's .env) so backup.sh connects as the role that owns
# the app databases instead of falling back to "<db>_app".
if [ -f "$SCRIPT_DIR/../.env" ]; then
  set -a; . "$SCRIPT_DIR/../.env"; set +a
fi

BACKUP_DATABASES="${BACKUP_DATABASES:-mindless_meals}"
export BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/postgres}"
LOCAL_COPY_MOUNT="${LOCAL_COPY_MOUNT:-/mnt/backupdrive}"
OFFSITE_REMOTE="${OFFSITE_REMOTE-gdrive-crypt:postgres}"
OFFSITE_RETENTION="${OFFSITE_RETENTION:-90d}"

failed=0
echo "=== Nightly backup started $(date -u +%Y-%m-%dT%H:%M:%SZ)"

for db in $BACKUP_DATABASES; do
  if ! "$SCRIPT_DIR/backup.sh" "$db"; then
    echo "ERROR: backup of '$db' failed"
    failed=1
  fi
done

# Copy 1: attached drive. Only if it is really mounted; otherwise rsync
# would write into the empty mount-point folder on Atlas's own disk.
if mountpoint -q "$LOCAL_COPY_MOUNT"; then
  mkdir -p "$LOCAL_COPY_MOUNT/postgres"
  # No --delete: removing a dump on Atlas must never remove the copy.
  if ! rsync -a --include '*.sql.gz' --exclude '*' "$BACKUP_DIR"/ "$LOCAL_COPY_MOUNT/postgres/"; then
    echo "ERROR: copy to $LOCAL_COPY_MOUNT failed"
    failed=1
  fi
else
  echo "WARNING: $LOCAL_COPY_MOUNT is not mounted; skipped local drive copy"
  failed=1
fi

# Copy 2: encrypted off-site remote. `copy`, never `sync`, so deletions on
# Atlas don't propagate.
if [ -n "$OFFSITE_REMOTE" ]; then
  if ! command -v rclone >/dev/null 2>&1; then
    echo "ERROR: rclone not installed; skipped off-site copy"
    failed=1
  elif ! rclone copy "$BACKUP_DIR" "$OFFSITE_REMOTE" --include '*.sql.gz'; then
    echo "ERROR: off-site copy to $OFFSITE_REMOTE failed"
    failed=1
  else
    rclone delete "$OFFSITE_REMOTE" --min-age "$OFFSITE_RETENTION" --include '*.sql.gz' \
      || echo "WARNING: off-site retention cleanup failed (copies are safe, just not pruned)"
  fi
fi

if [ "$failed" -eq 0 ]; then
  echo "=== Nightly backup OK $(date -u +%Y-%m-%dT%H:%M:%SZ)"
else
  echo "=== Nightly backup finished WITH ERRORS $(date -u +%Y-%m-%dT%H:%M:%SZ)"
fi
exit "$failed"
