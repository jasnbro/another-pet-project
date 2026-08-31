#!/usr/bin/env bash
# Provisions one application's database + least-privilege role on the
# shared postgres server, via `docker exec` into the running container.
# This is the one mechanism used to onboard every app database on this
# server -- the first one (mindless_meals) and every one after it
# (the_budget, ...) -- run by hand, once per app. See
# postgres/init/README.md for why this isn't done via
# docker-entrypoint-initdb.d instead.
#
# Usage:
#   ./create_app_database.sh <db_name> [role_name]
#
# role_name defaults to "<db_name>_app" (this server's naming convention,
# e.g. mindless_meals -> mindless_meals_app).
#
# What this does, in order (each step only if not already true --
# idempotent, safe to re-run):
#   1. CREATE ROLE <role> LOGIN PASSWORD '<random>'
#   2. CREATE DATABASE <db> OWNER <role>
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
#   POSTGRES_ADMIN_USER    Superuser role to connect as (default: postgres --
#                           i.e. whatever POSTGRES_USER was set to when the
#                           server was first initialized)
#   APP_DB_PASSWORD         Use this exact password instead of generating one
#                           (only takes effect when the role doesn't exist yet)
#
# Requires `openssl` on the host (used to generate the password) --
# present by default on Ubuntu.
set -euo pipefail

DB_NAME="${1:?Usage: create_app_database.sh <db_name> [role_name]}"
ROLE_NAME="${2:-${DB_NAME}_app}"
CONTAINER="${POSTGRES_CONTAINER:-postgres}"
ADMIN_USER="${POSTGRES_ADMIN_USER:-postgres}"

for identifier in "$DB_NAME" "$ROLE_NAME"; do
  if ! [[ "$identifier" =~ ^[a-z][a-z0-9_]*$ ]]; then
    echo "Invalid identifier: '$identifier' (lowercase letters/digits/underscore, starting with a letter, only)" >&2
    exit 1
  fi
done

run_sql() {
  docker exec -i "$CONTAINER" psql -U "$ADMIN_USER" -v ON_ERROR_STOP=1 -tAc "$1"
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
  echo "Database '${DB_NAME}' already exists -- leaving it as-is."
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
  echo "  postgresql://${ROLE_NAME}:${new_password}@postgres:5432/${DB_NAME}"
else
  echo
  echo "DATABASE_URL (using the existing password, not shown by this script):"
  echo "  postgresql://${ROLE_NAME}:<password>@postgres:5432/${DB_NAME}"
fi
