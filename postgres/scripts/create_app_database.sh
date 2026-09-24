#!/usr/bin/env bash
# Provisions one application's database + least-privilege role on the
# shared postgres server, via `docker exec` into the running container.
#
# NOT what the real Atlas deployment currently does: it reuses one
# shared superuser role for every app's database instead (simpler --
# see postgres/README.md, which also names this per-app-role approach
# as the alternative if tighter isolation is ever needed). This script
# is that alternative.
#
# Run by hand against the running container (not via
# docker-entrypoint-initdb.d, which only fires once, on a data
# directory's first init -- useless for onboarding an app added later).
#
# Usage:
#   ./create_app_database.sh <db_name> [role_name]
#
# role_name defaults to "<db_name>_app" (this server's naming convention,
# e.g. mindless_meals -> mindless_meals_app).
#
# What this does, in order (each step only if not already true --
# idempotent, safe to re-run):
#   1. CREATE ROLE <role> LOGIN PASSWORD '<random>'      (if it doesn't exist)
#   2. If <db> doesn't exist yet: CREATE DATABASE <db> OWNER <role>
#      If <db> already exists (e.g. it was created under the old shared
#      superuser, before this app was switched to its own role):
#        a. ALTER DATABASE <db> OWNER TO <role>
#        b. Reassign every table/sequence/view/materialized view inside
#           <db> still owned by <old_owner> to <role>, run *inside* <db>
#           via individual ALTER ... OWNER TO statements -- (a) only
#           reassigns the database object itself; the tables, sequences,
#           etc. already inside it are still owned by whoever created
#           them until this step reassigns those too. Skipped if <db>
#           already belongs to <role>.
#
#           This does NOT use `REASSIGN OWNED BY <old_owner> TO <role>`,
#           which looks like the obvious tool for this: Postgres
#           unconditionally refuses it with "cannot reassign ownership
#           of objects owned by role ... because they are required by
#           the database system" whenever <old_owner> is the cluster's
#           bootstrap superuser -- and on the official postgres image,
#           POSTGRES_USER *is* that bootstrap role (verify with
#           `SELECT oid FROM pg_roles WHERE rolname = '<POSTGRES_USER>'`;
#           the bootstrap role always has oid 10), which is exactly
#           who owns every app's database today. Per-object ALTER ...
#           OWNER TO has no such restriction.
#   3. REVOKE CONNECT ON DATABASE <db> FROM PUBLIC
#   4. GRANT CONNECT ON DATABASE <db> TO <role>
#
# Steps 3-4 matter: Postgres grants every role CONNECT to every database
# by default. Without revoking it, e.g. mindless_meals_app could still
# *connect* to the_budget's database (though it couldn't read anything
# inside it without further grants) -- revoking PUBLIC's CONNECT closes
# that off outright, so cross-app isolation doesn't depend on nobody ever
# granting the wrong thing later.
#
# The generated password is printed once, to copy into that app's Doppler
# config (or local .env for dev) -- it is never written to disk or logged
# by this script. Re-running against an existing role does NOT reset its
# password.
#
# Configuration (environment variables):
#   POSTGRES_CONTAINER   Container name/ID to exec into (default: postgres)
#   POSTGRES_ADMIN_USER    Superuser role to connect as -- defaults to
#                           POSTGRES_USER (whatever the server's superuser
#                           was set to at first init -- see
#                           postgres/README.md), falling back to "postgres"
#                           if that isn't set either
#   APP_DB_PASSWORD         Use this exact password instead of generating one
#                           (only takes effect when the role doesn't exist yet)
#
# Requires `openssl` on the host (used to generate the password) --
# present by default on Ubuntu.
set -euo pipefail

DB_NAME="${1:?Usage: create_app_database.sh <db_name> [role_name]}"
ROLE_NAME="${2:-${DB_NAME}_app}"
CONTAINER="${POSTGRES_CONTAINER:-postgres}"
ADMIN_USER="${POSTGRES_ADMIN_USER:-${POSTGRES_USER:-postgres}}"

for identifier in "$DB_NAME" "$ROLE_NAME"; do
  if ! [[ "$identifier" =~ ^[a-z][a-z0-9_]*$ ]]; then
    echo "Invalid identifier: '$identifier' (lowercase letters/digits/underscore, starting with a letter, only)" >&2
    exit 1
  fi
done

# Always connect to the "postgres" administrative database explicitly --
# `psql -U $ADMIN_USER` with no -d defaults to a database *named after
# the user* (e.g. "madamada"), which doesn't exist on this server and
# would fail outright.
run_sql() {
  docker exec -i "$CONTAINER" psql -U "$ADMIN_USER" -d postgres -v ON_ERROR_STOP=1 -tAc "$1"
}

# Ownership reassignment only affects objects in the database you're
# currently connected to, so this one needs a real -d <app db>, not
# the admin database.
run_sql_in_db() {
  docker exec -i "$CONTAINER" psql -U "$ADMIN_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -tAc "$1"
}

# Reassigns every table/sequence/view/matview in $DB_NAME still owned by
# $1 to $ROLE_NAME, via per-object ALTER ... OWNER TO rather than
# REASSIGN OWNED BY (see the usage comment above for why). Scoped to
# objects actually owned by $1, and to non-system schemas, so it never
# touches anything outside what REASSIGN OWNED BY would itself have
# touched.
#
# Sequences created by SERIAL/IDENTITY columns are excluded: Postgres
# ties such a sequence to its owning column (pg_depend deptype 'a'/'i')
# and refuses a direct ALTER SEQUENCE ... OWNER TO on it ("cannot change
# owner of sequence ... is linked to table ...") -- reassigning the
# TABLE's owner cascades to that sequence automatically, so it needs no
# separate statement. Only genuinely standalone sequences are reassigned
# here.
reassign_owned_objects() {
  local old_owner="$1"
  run_sql_in_db "
DO \$reassign\$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT 'ALTER ' ||
           CASE c.relkind
             WHEN 'S' THEN 'SEQUENCE'
             WHEN 'v' THEN 'VIEW'
             WHEN 'm' THEN 'MATERIALIZED VIEW'
             ELSE 'TABLE'
           END || ' ' || quote_ident(n.nspname) || '.' || quote_ident(c.relname)
           || ' OWNER TO ' || quote_ident('${ROLE_NAME}') AS stmt
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_roles ro ON ro.oid = c.relowner
    WHERE c.relkind IN ('r', 'p', 'S', 'v', 'm')
      AND ro.rolname = '${old_owner}'
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
      AND NOT (
        c.relkind = 'S'
        AND EXISTS (
          SELECT 1 FROM pg_depend d
          WHERE d.objid = c.oid AND d.deptype IN ('a', 'i')
        )
      )
  LOOP
    EXECUTE r.stmt;
  END LOOP;
END
\$reassign\$;
" >/dev/null
}

role_exists="$(run_sql "SELECT 1 FROM pg_roles WHERE rolname = '${ROLE_NAME}'")"
db_exists="$(run_sql "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'")"

new_password=""
if [ "$role_exists" = "1" ]; then
  echo "Role '${ROLE_NAME}' already exists -- leaving its password unchanged."
else
  new_password="${APP_DB_PASSWORD:-$(openssl rand -hex 24)}"
  echo "Creating role '${ROLE_NAME}'..."
  run_sql "CREATE ROLE ${ROLE_NAME} LOGIN PASSWORD '${new_password}';" >/dev/null
fi

if [ "$db_exists" = "1" ]; then
  current_owner="$(run_sql "SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_database WHERE datname = '${DB_NAME}'")"
  if [ "$current_owner" = "$ROLE_NAME" ]; then
    echo "Database '${DB_NAME}' already owned by '${ROLE_NAME}' -- leaving it as-is."
  else
    echo "Database '${DB_NAME}' already exists, owned by '${current_owner}' -- adopting it into '${ROLE_NAME}'..."
    run_sql "ALTER DATABASE ${DB_NAME} OWNER TO ${ROLE_NAME};" >/dev/null
    echo "Reassigning objects inside '${DB_NAME}' (tables, sequences, ...) from '${current_owner}' to '${ROLE_NAME}'..."
    reassign_owned_objects "${current_owner}"
  fi
else
  echo "Creating database '${DB_NAME}' owned by '${ROLE_NAME}'..."
  run_sql "CREATE DATABASE ${DB_NAME} OWNER ${ROLE_NAME};" >/dev/null
fi

echo "Restricting '${DB_NAME}' to '${ROLE_NAME}' only (revoking PUBLIC CONNECT)..."
run_sql "REVOKE CONNECT ON DATABASE ${DB_NAME} FROM PUBLIC;" >/dev/null
run_sql "GRANT CONNECT ON DATABASE ${DB_NAME} TO ${ROLE_NAME};" >/dev/null

echo
echo "Done. '${ROLE_NAME}' owns '${DB_NAME}' and cannot connect to any other database on this server."
if [ -n "$new_password" ]; then
  echo
  echo "Generated password for '${ROLE_NAME}' -- copy into ${DB_NAME}'s Doppler config now, shown once:"
  echo "  ${new_password}"
  echo
  echo "DATABASE_URL:"
  echo "  postgresql+psycopg2://${ROLE_NAME}:${new_password}@postgres:5432/${DB_NAME}"
else
  echo
  echo "DATABASE_URL (using the existing password, not shown by this script):"
  echo "  postgresql+psycopg2://${ROLE_NAME}:<password>@postgres:5432/${DB_NAME}"
fi
