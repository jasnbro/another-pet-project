#!/usr/bin/env bash
# Proves a backup actually restores: restores the newest backup of a
# database into a throwaway scratch database, compares every table's row
# count with the live database, then drops the scratch database. The live
# database is only read (one SELECT of counts), never written.
#
# Usage:
#   ./restore_test.sh <database_name> [backup_file]
#     backup_file defaults to the newest <database_name>_*.sql.gz[.age]
#     in BACKUP_DIR.
#
# Fails (non-zero) if the restore errors, if a table is missing from the
# restore, or if a table that has rows in the live database restored empty.
# Other count differences are printed as "changed since backup" -- the live
# database keeps moving after the dump was taken -- but don't fail the test.
#
# Configuration (environment variables):
#   BACKUP_DIR          Where to look for backups (default: ./backups next to
#                       this script)
#   POSTGRES_CONTAINER  Container to exec into (default: postgres)
#   DB_ROLE             Must be able to CREATE/DROP DATABASE: the
#                       POSTGRES_USER superuser (default: POSTGRES_USER)
#   KEEP_SCRATCH=1      Leave the scratch database in place for inspection
#   BACKUP_AGE_IDENTITY / BACKUP_AGE_IDENTITY_FILE   for .age backups, as in
#                       restore.sh
set -euo pipefail

DB_NAME="${1:?Usage: restore_test.sh <database_name> [backup_file]}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR/../backups}"
CONTAINER="${POSTGRES_CONTAINER:-postgres}"
DB_ROLE="${DB_ROLE:-${POSTGRES_USER:?set DB_ROLE or POSTGRES_USER to a role that can create databases}}"
SCRATCH="${DB_NAME}_restore_test"

die() { echo "restore_test.sh: ERROR: $*" >&2; exit 1; }

[[ "$DB_NAME" =~ ^[a-z_][a-z0-9_]*$ ]] || die "unexpected database name: $DB_NAME"

if [ $# -ge 2 ]; then
  BACKUP_FILE="$2"
else
  # Timestamps are fixed-width UTC, so name order is time order.
  BACKUP_FILE="$(find "$BACKUP_DIR" -maxdepth 1 -type f \
      \( -name "${DB_NAME}_[0-9]*T[0-9]*Z.sql.gz" -o -name "${DB_NAME}_[0-9]*T[0-9]*Z.sql.gz.age" \) \
      2>/dev/null | sort | tail -n 1)"
  [ -n "$BACKUP_FILE" ] || die "no backups of '$DB_NAME' found in $BACKUP_DIR"
fi

psql_c() { # database, sql -> unaligned, tuples-only output
  docker exec -i "$CONTAINER" psql -X -q -At -U "$DB_ROLE" -v ON_ERROR_STOP=1 -d "$1" -c "$2"
}

# Exact row count of every user table, "schema.table|count", sorted.
COUNTS_SQL="SELECT table_schema || '.' || table_name || '|' ||
  (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I',
    table_schema, table_name), false, true, '')))[1]::text
FROM information_schema.tables
WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY 1"

drop_scratch() { psql_c postgres "DROP DATABASE IF EXISTS \"$SCRATCH\"" >/dev/null; }

echo "Restore test: $BACKUP_FILE -> scratch database '$SCRATCH'"
# The scratch name is reserved for this script, so a leftover from an
# earlier interrupted run is safe to drop.
drop_scratch
psql_c postgres "CREATE DATABASE \"$SCRATCH\"" >/dev/null
if [ "${KEEP_SCRATCH:-}" != 1 ]; then trap drop_scratch EXIT; fi

DB_ROLE="$DB_ROLE" POSTGRES_CONTAINER="$CONTAINER" "$SCRIPT_DIR/restore.sh" "$BACKUP_FILE" "$SCRATCH"

live="$(psql_c "$DB_NAME" "$COUNTS_SQL")"
restored="$(psql_c "$SCRATCH" "$COUNTS_SQL")"

problems=0; changed=0; tables=0
while IFS='|' read -r table live_n; do
  [ -n "$table" ] || continue
  tables=$((tables + 1))
  restored_n="$(printf '%s\n' "$restored" | awk -F'|' -v t="$table" '$1 == t { print $2 }')"
  if [ -z "$restored_n" ]; then
    echo "  MISSING  $table (live: $live_n rows)"; problems=$((problems + 1))
  elif [ "$restored_n" -eq 0 ] && [ "$live_n" -gt 0 ]; then
    echo "  EMPTY    $table (live: $live_n rows, restored: 0)"; problems=$((problems + 1))
  elif [ "$restored_n" -ne "$live_n" ]; then
    echo "  changed  $table (live: $live_n, restored: $restored_n -- changed since backup)"; changed=$((changed + 1))
  else
    echo "  ok       $table ($live_n rows)"
  fi
done <<< "$live"

[ "$tables" -gt 0 ] || die "live database '$DB_NAME' has no tables -- nothing to compare"

if [ "$problems" -gt 0 ]; then
  die "restore test FAILED: $problems problem(s) across $tables tables (backup: $BACKUP_FILE)"
fi
echo "Restore test PASSED: $tables tables restored ($changed changed since backup)."
if [ "${KEEP_SCRATCH:-}" = 1 ]; then echo "Scratch database '$SCRATCH' kept (KEEP_SCRATCH=1)."; fi
