#!/usr/bin/env bash
# Restores a gzip'd plain-SQL backup (see backup.sh) into a database via
# the running `postgres` container.
#
# Usage:
#   ./restore.sh <backup_file.sql.gz> [database_name]
#
# The target database must already exist. Restoring into a database that
# already has tables in it will fail partway through on the first
# conflicting object rather than silently overwrite data -- create a
# fresh, empty database first (see postgres/README.md, which also covers
# testing a restore into a throwaway database before you ever need this
# for real -- or use test_restore.sh, which automates exactly that).
#
# Configuration (environment variables):
#   POSTGRES_CONTAINER   Container name/ID to exec into (default: postgres)
#   DB_ROLE                Role to connect as -- must own (or otherwise have
#                           full write access to) the target database; the
#                           app role that owns it (see create_app_database.sh)
#                           always qualifies (default: "<database_name>_app")
set -euo pipefail

BACKUP_FILE="${1:?Usage: restore.sh <backup_file.sql.gz> [database_name]}"
DB_NAME="${2:-mindless_meals}"
CONTAINER="${POSTGRES_CONTAINER:-postgres}"
DB_ROLE="${DB_ROLE:-${DB_NAME}_app}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

echo "Restoring $BACKUP_FILE into database '${DB_NAME}' (role '${DB_ROLE}') via container '${CONTAINER}'"
echo "(target database must already exist and be empty -- see postgres/README.md)"

gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER" psql -U "$DB_ROLE" -v ON_ERROR_STOP=1 "$DB_NAME"

echo "Restore complete. Sanity-check row counts, e.g.:"
echo "  docker exec $CONTAINER psql -U $DB_ROLE -d $DB_NAME -c 'SELECT count(*) FROM recipes;'"
