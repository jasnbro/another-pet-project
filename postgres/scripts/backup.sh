#!/usr/bin/env bash
# Backs up one or more Postgres databases from the running `postgres`
# container via `docker exec pg_dump`, writing a timestamped,
# gzip-compressed plain-SQL dump per database to BACKUP_DIR. Plain SQL (not
# pg_dump's custom format) so a backup can be inspected or restored with
# nothing more than psql/zcat -- see postgres/README.md#backups.
#
# Usage:
#   ./backup.sh [database_name ...]        # default: mindless_meals
#
# For the nightly job use nightly_backup.sh, which turns on encryption and
# the SSD mount guard and refuses to run without them. This script keeps
# both optional so deploy/deploy.sh's pre-migration backup works unchanged.
#
# Configuration (environment variables, all optional):
#   POSTGRES_CONTAINER   Container name/ID to exec into (default: postgres)
#   DB_ROLE              Role to connect as -- must have read access to every
#                        table. Defaults to POSTGRES_USER, falling back to
#                        "<database_name>_app" (see postgres/README.md)
#   BACKUP_DIR           Where dumps are written (default: ./backups next to
#                        this script)
#   RETENTION_DAYS       Delete this database's dumps older than N days after
#                        a successful backup (default: 14; 0 disables)
#   BACKUP_AGE_RECIPIENT age public key (age1...). When set, each dump is
#                        encrypted and written as .sql.gz.age; nothing
#                        unencrypted touches the disk. Only the public key is
#                        needed here -- the private key is needed to restore.
#   BACKUP_REQUIRE_MOUNT A mount point (e.g. /mnt/backup-ssd). When set, the
#                        script refuses to write anything unless that path is
#                        a mounted filesystem AND BACKUP_DIR is inside it, so
#                        an unplugged SSD can never send backups to the main
#                        disk.
#
# Exit status is non-zero if any database fails; the others still run.
set -euo pipefail

CONTAINER="${POSTGRES_CONTAINER:-postgres}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR/../backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
RECIPIENT="${BACKUP_AGE_RECIPIENT:-}"
REQUIRE_MOUNT="${BACKUP_REQUIRE_MOUNT:-}"

die() { echo "backup.sh: ERROR: $*" >&2; exit 1; }

if [ $# -eq 0 ]; then set -- mindless_meals; fi

# --- Mount guard: runs before anything is created on disk ---------------
if [ -n "$REQUIRE_MOUNT" ]; then
  mountpoint -q "$REQUIRE_MOUNT" \
    || die "$REQUIRE_MOUNT is not a mounted filesystem (is the backup SSD plugged in?). Nothing was written."
  mount_real="$(realpath "$REQUIRE_MOUNT")"
  # realpath -m: BACKUP_DIR may not exist yet; resolve without requiring it.
  dir_real="$(realpath -m "$BACKUP_DIR")"
  case "$dir_real/" in
    "$mount_real"/*) ;;
    *) die "BACKUP_DIR ($dir_real) is not inside $mount_real. Nothing was written." ;;
  esac
fi

if [ -n "$RECIPIENT" ]; then
  command -v age >/dev/null || die "BACKUP_AGE_RECIPIENT is set but 'age' is not installed (sudo apt install age)."
  case "$RECIPIENT" in age1*) ;; *) die "BACKUP_AGE_RECIPIENT doesn't look like an age public key (age1...)." ;; esac
fi

mkdir -p "$BACKUP_DIR"

backup_one() { # runs in a subshell, so the trap and variables are per-database
  local db="$1" role="${DB_ROLE:-${POSTGRES_USER:-${1}_app}}" ext=sql.gz
  if [ -n "$RECIPIENT" ]; then ext=sql.gz.age; fi
  local timestamp out_file
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out_file="$BACKUP_DIR/${db}_${timestamp}.${ext}"
  tmp_file="${out_file}.partial"
  # shellcheck disable=SC2064  # expand now: remove this database's partial file
  trap "rm -f '$tmp_file'" EXIT

  echo "Backing up database '${db}' (as role '${role}') from container '${CONTAINER}'"
  echo "  -> ${out_file}"

  # Dump to a .partial name first so a crash/kill mid-backup never leaves a
  # truncated file with a "real" backup's name.
  # Every step checks its own status: `set -e` is ignored inside a function
  # called from an `if`, which is how the loop below runs this.
  if [ -n "$RECIPIENT" ]; then
    docker exec "$CONTAINER" pg_dump -U "$role" --no-owner --no-privileges "$db" \
      | gzip | age -r "$RECIPIENT" > "$tmp_file" || return 1
  else
    docker exec "$CONTAINER" pg_dump -U "$role" --no-owner --no-privileges "$db" \
      | gzip > "$tmp_file" || return 1
  fi
  mv "$tmp_file" "$out_file" || return 1
  echo "Wrote $(du -h "$out_file" | cut -f1) to $out_file"

  if [ "$RETENTION_DAYS" -gt 0 ]; then
    echo "Removing '${db}' backups older than ${RETENTION_DAYS} day(s) in ${BACKUP_DIR}..."
    # The timestamp in the pattern keeps "mindless_meals" from matching
    # backups of a database named e.g. "mindless_meals_restored".
    find "$BACKUP_DIR" -maxdepth 1 -type f \
      \( -name "${db}_[0-9]*T[0-9]*Z.sql.gz" -o -name "${db}_[0-9]*T[0-9]*Z.sql.gz.age" \) \
      -mtime "+${RETENTION_DAYS}" -print -delete || return 1
  fi
}

failed=()
for db in "$@"; do
  # Subshell so one database's failure (set -e) doesn't stop the rest.
  if ! ( backup_one "$db" ); then
    echo "backup.sh: ERROR: backup of '${db}' FAILED" >&2
    failed+=("$db")
  fi
done

if [ ${#failed[@]} -gt 0 ]; then
  die "${#failed[@]} database(s) failed: ${failed[*]}"
fi
echo "Done."
