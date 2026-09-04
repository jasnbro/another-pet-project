#!/usr/bin/env bash
# Backs up one Postgres database from the running `postgres` container via
# `docker exec pg_dump`, writing a timestamped, gzip-compressed plain-SQL
# dump to BACKUP_DIR. Plain SQL (not pg_dump's custom format) so a backup
# can be inspected or restored with nothing more than psql/zcat -- see
# postgres/README.md#backups for the reasoning.
#
# Usage:
#   ./backup.sh [database_name]
#
# Configuration (environment variables, all optional):
#   POSTGRES_CONTAINER   Container name/ID to exec into (default: postgres)
#   DB_ROLE                Role to connect as -- must have read access to every
#                           table in the database; that database's owning
#                           app role (see create_app_database.sh) always
#                           qualifies (default: "<database_name>_app", this
#                           server's naming convention)
#   BACKUP_DIR             Where dumps are written (default: ./backups next to this script)
#   RETENTION_DAYS         Delete this database's dumps older than N days after
#                           a successful backup (default: 14; set to 0 to disable)
#
# Example cron entry (daily at 2am, off-Atlas copies handled separately --
# see postgres/README.md#backups) -- see install_cron.sh to set this up:
#   0 2 * * * BACKUP_DIR=/home/jasmine/backups/postgres /home/jasmine/services/postgres/scripts/backup.sh mindless_meals >> /home/jasmine/backups/postgres/backup.log 2>&1
set -euo pipefail

DB_NAME="${1:-mindless_meals}"
CONTAINER="${POSTGRES_CONTAINER:-postgres}"
DB_ROLE="${DB_ROLE:-${DB_NAME}_app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR/../backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
out_file="$BACKUP_DIR/${DB_NAME}_${timestamp}.sql.gz"
tmp_file="${out_file}.partial"

echo "Backing up database '${DB_NAME}' (as role '${DB_ROLE}') from container '${CONTAINER}'"
echo "  -> ${out_file}"

# Dump to a .partial name first so a crash/kill mid-backup never leaves a
# truncated file with a "real" backup's name.
docker exec "$CONTAINER" pg_dump -U "$DB_ROLE" --no-owner --no-privileges "$DB_NAME" | gzip > "$tmp_file"
mv "$tmp_file" "$out_file"

echo "Wrote $(du -h "$out_file" | cut -f1) to $out_file"

if [ "$RETENTION_DAYS" -gt 0 ]; then
  echo "Removing '${DB_NAME}' backups older than ${RETENTION_DAYS} day(s) in ${BACKUP_DIR}..."
  find "$BACKUP_DIR" -maxdepth 1 -type f -name "${DB_NAME}_*.sql.gz" -mtime "+${RETENTION_DAYS}" -print -delete
fi

echo "Done."
