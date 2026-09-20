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
# for real). There is no automated restore-test script yet -- run the
# same steps by hand periodically.
#
# Configuration (environment variables):
#   POSTGRES_CONTAINER   Container name/ID to exec into (default: postgres)
#   DB_ROLE                Role to connect as -- must own (or otherwise have
#                           full write access to) the target database.
#                           Defaults to POSTGRES_USER (the shared superuser
#                           every app's database is currently owned by --
#                           see postgres/README.md), falling back to
#                           "<database_name>_app" if POSTGRES_USER isn't set
#                           either (the per-app-role convention
#                           create_app_database.sh sets up, not yet adopted
#                           for the real deployment)
set -euo pipefail

BACKUP_FILE="${1:?Usage: restore.sh <backup_file.sql.gz> [database_name]}"
DB_NAME="${2:-mindless_meals}"
CONTAINER="${POSTGRES_CONTAINER:-postgres}"
DB_ROLE="${DB_ROLE:-${POSTGRES_USER:-${DB_NAME}_app}}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

echo "Restoring $BACKUP_FILE into database '${DB_NAME}' (role '${DB_ROLE}') via container '${CONTAINER}'"
echo "(target database must already exist and be empty -- see postgres/README.md)"

gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER" psql -U "$DB_ROLE" -v ON_ERROR_STOP=1 "$DB_NAME"

echo "Restore complete. Sanity-check row counts, e.g.:"
echo "  docker exec $CONTAINER psql -U $DB_ROLE -d $DB_NAME -c 'SELECT count(*) FROM recipes;'"
