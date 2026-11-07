#!/usr/bin/env bash
# Backs up one or more Postgres databases from the running `postgres` container via
# `docker exec pg_dump`, writing a timestamped, gzip-compressed plain-SQL
# dump to BACKUP_DIR. Plain SQL (not pg_dump's custom format) so a backup
# can be inspected or restored with nothing more than psql/zcat -- see
# postgres/README.md#backups for the reasoning.
#
# Usage:
#   ./backup.sh [database_name ...]        (default: mindless_meals)
#   ./backup.sh mindless_meals gym_log     # every app database, one run
#
# Configuration (environment variables, all optional):
#   POSTGRES_CONTAINER   Container name/ID to exec into (default: postgres)
#   DB_ROLE                Role to connect as, for every database named -- must
#                           have read access to every table. Defaults to POSTGRES_USER
#                           (the shared superuser every app's database is
#                           currently owned by -- see postgres/README.md),
#                           falling back to "<database_name>_app" if
#                           POSTGRES_USER isn't set either (the per-app-role
#                           convention create_app_database.sh sets up, not
#                           yet adopted for the real deployment), worked
#                           out separately for each database
#   BACKUP_DIR             Where dumps are written (default: ./backups next to this script)
#   RETENTION_DAYS         Delete this database's dumps older than N days after
#                           a successful backup (default: 14; set to 0 to disable)
#
# Example cron entry (daily at 2am, off-Atlas copies handled separately --
# see postgres/README.md#backups). No installer script for this yet --
# add it with `crontab -e`:
#   0 2 * * * BACKUP_DIR=/home/jasmine/backups/postgres /home/jasmine/services/postgres/scripts/backup.sh mindless_meals gym_log >> /home/jasmine/backups/postgres/backup.log 2>&1
#
# With several databases, each is dumped in turn; the script stops at the
# first failure (exit non-zero), and every dump written before it is kept.
set -euo pipefail

if [ "$#" -eq 0 ]; then set -- mindless_meals; fi
CONTAINER="${POSTGRES_CONTAINER:-postgres}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR/../backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

backup_one() {
  local db_name="$1"
  local db_role="${DB_ROLE:-${POSTGRES_USER:-${db_name}_app}}"
  local timestamp out_file tmp_file
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out_file="$BACKUP_DIR/${db_name}_${timestamp}.sql.gz"
  tmp_file="${out_file}.partial"

  echo "Backing up database '${db_name}' (as role '${db_role}') from container '${CONTAINER}'"
  echo "  -> ${out_file}"

  # Dump to a .partial name first so a crash/kill mid-backup never leaves a
  # truncated file with a "real" backup's name.
  docker exec "$CONTAINER" pg_dump -U "$db_role" --no-owner --no-privileges "$db_name" | gzip > "$tmp_file"
  mv "$tmp_file" "$out_file"

  echo "Wrote $(du -h "$out_file" | cut -f1) to $out_file"

  if [ "$RETENTION_DAYS" -gt 0 ]; then
    echo "Removing '${db_name}' backups older than ${RETENTION_DAYS} day(s) in ${BACKUP_DIR}..."
    find "$BACKUP_DIR" -maxdepth 1 -type f -name "${db_name}_*.sql.gz" -mtime "+${RETENTION_DAYS}" -print -delete
  fi
}

for db_name in "$@"; do
  backup_one "$db_name"
done

echo "Done."
