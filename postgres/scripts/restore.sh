#!/usr/bin/env bash
# Restores a backup made by backup.sh (.sql.gz, or encrypted .sql.gz.age)
# into a database via the running `postgres` container.
#
# Usage:
#   ./restore.sh <backup_file> [database_name]      # default: mindless_meals
#
# The target database must already exist. Restoring into a database that
# already has tables in it fails on the first conflicting object rather than
# silently overwriting data -- create a fresh, empty database first, or use
# restore_test.sh, which does that for you and checks the result.
#
# Configuration (environment variables):
#   POSTGRES_CONTAINER        Container name/ID to exec into (default: postgres)
#   DB_ROLE                   Role to connect as -- must own (or have full
#                             write access to) the target database. Defaults
#                             to POSTGRES_USER, falling back to
#                             "<database_name>_app" (see postgres/README.md)
#   For .age backups, one of:
#   BACKUP_AGE_IDENTITY       The age private key itself (AGE-SECRET-KEY-...),
#                             e.g. injected by `doppler run`. Never written to
#                             disk.
#   BACKUP_AGE_IDENTITY_FILE  Path to a file holding it (e.g. the offline
#                             recovery copy on a USB stick).
set -euo pipefail

BACKUP_FILE="${1:?Usage: restore.sh <backup_file> [database_name]}"
DB_NAME="${2:-mindless_meals}"
CONTAINER="${POSTGRES_CONTAINER:-postgres}"
DB_ROLE="${DB_ROLE:-${POSTGRES_USER:-${DB_NAME}_app}}"

die() { echo "restore.sh: ERROR: $*" >&2; exit 1; }

[ -f "$BACKUP_FILE" ] || die "backup file not found: $BACKUP_FILE"

decompress() {
  case "$BACKUP_FILE" in
    *.sql.gz.age)
      command -v age >/dev/null || die "'age' is not installed (sudo apt install age)"
      if [ -n "${BACKUP_AGE_IDENTITY:-}" ]; then
        # Process substitution: the key goes through a pipe, not a file.
        age -d -i <(printf '%s\n' "$BACKUP_AGE_IDENTITY") "$BACKUP_FILE" | gunzip -c
      elif [ -n "${BACKUP_AGE_IDENTITY_FILE:-}" ]; then
        age -d -i "$BACKUP_AGE_IDENTITY_FILE" "$BACKUP_FILE" | gunzip -c
      else
        die "encrypted backup: set BACKUP_AGE_IDENTITY (via doppler run) or BACKUP_AGE_IDENTITY_FILE"
      fi ;;
    *.sql.gz) gunzip -c "$BACKUP_FILE" ;;
    *) die "unrecognised backup file type: $BACKUP_FILE (expected .sql.gz or .sql.gz.age)" ;;
  esac
}

echo "Restoring $BACKUP_FILE into database '${DB_NAME}' (role '${DB_ROLE}') via container '${CONTAINER}'"
echo "(target database must already exist and be empty -- see postgres/README.md)"

decompress | docker exec -i "$CONTAINER" psql -q -U "$DB_ROLE" -v ON_ERROR_STOP=1 -d "$DB_NAME" >/dev/null

echo "Restore complete."
