#!/usr/bin/env bash
# Deploy one revision of an app (default Mindless Meals) on ATLAS.
#
#   deploy/deploy.sh <git sha>
#   APP=gym_log deploy/deploy.sh <git sha>
#
# Run from a checkout of that revision (the GitHub Actions runner does this;
# see deploy/README.md). Steps:
#   1. Build mindless_meals:<sha> from this checkout.
#   2. If on Postgres: refuse unless the database is under Alembic (or is
#      completely empty, for an app's first deploy), back it up, then apply
#      any pending migrations with the NEW image.
#   3. Switch the container to the new image and wait for its health check.
#   4. If it isn't healthy, switch back to the previous image and fail.
#
# Never touches other services, ./data, or .env. Safe to re-run.
#
# Env overrides: APP (default mindless_meals), SERVICE_DIR (default ~/services/$APP),
# BACKUP_DIR (default ~/backups/postgres), HEALTH_TIMEOUT (default 90s),
# KEEP_IMAGES (default 5).
set -euo pipefail
# shellcheck source=deploy/common.sh
source "$(dirname "$0")/common.sh"

SHA="${1:?usage: deploy.sh <git sha>}"
TAG="${SHA:0:12}"
IMAGE="$APP:$TAG"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/postgres}"
KEEP_IMAGES="${KEEP_IMAGES:-5}"
# Prints how many tables DATABASE_URL's database has (run in the new image).
COUNT_TABLES='import os, sqlalchemy as sa; print(len(sa.inspect(sa.create_engine(os.environ["DATABASE_URL"])).get_table_names()))'

take_lock
log "Deploying $IMAGE to $SERVICE_DIR"

# --- Preflight: fail before changing anything ---------------------------
[[ -f "$SERVICE_DIR/.env" ]] || die "$SERVICE_DIR/.env not found (it holds DATABASE_URL and is never in git)"
for net in atlas-proxy postgres_default; do
  docker network inspect "$net" >/dev/null 2>&1 || die "Docker network '$net' is missing"
done
# Apps using shared Undercurrent sign-in need the shared identity database;
# without it they would keep accounts in a throwaway file inside the container.
if [[ -d "$REPO_DIR/$APP/app/undercurrent_identity" ]] \
   && grep -qE '^DATABASE_URL=["'"'"']?postgresql' "$SERVICE_DIR/.env" \
   && ! grep -qE '^IDENTITY_DATABASE_URL=["'"'"']?postgresql' "$SERVICE_DIR/.env"; then
  die "$APP uses Undercurrent sign-in: set IDENTITY_DATABASE_URL (and IDENTITY_RP_ID, IDENTITY_COOKIE_DOMAIN, IDENTITY_PUBLIC_URL) in $SERVICE_DIR/.env first. See shared/undercurrent-identity/README.md. Nothing was changed."
fi

# --- 1. Build ------------------------------------------------------------
# --pull refreshes the base image so OS and Python security patches land on every deploy.
docker build --pull --label "org.opencontainers.image.revision=$SHA" -t "$IMAGE" "$REPO_DIR/$APP"

previous="$(running_image)"
log "Currently running: ${previous:-nothing}"

# --- 2. Database: back up, then migrate -----------------------------------
db_url="$(grep -E '^DATABASE_URL=' "$SERVICE_DIR/.env" | tail -n 1 | cut -d= -f2- | tr -d "\"'" || true)"
if [[ "$db_url" == postgresql* ]]; then
  # Run Alembic in the NEW image, with the service's real .env and networks,
  # without touching the running container.
  candidate="$STATE_DIR/candidate.yml"
  printf 'services:\n  %s:\n    image: %s\n' "$APP" "$IMAGE" > "$candidate"
  # Uses the repo's compose file in place; the service dir isn't modified
  # until the switch below.
  alembic() { docker compose -p "$APP" --project-directory "$SERVICE_DIR" \
      -f "$REPO_DIR/$APP/compose.yml" -f "$candidate" \
      run --rm --no-deps -T "$APP" alembic "$@"; }

  current_out="$(alembic current 2>&1)" || die "couldn't check the database's migration state (is Postgres up?):
$current_out"
  current_rev="$(grep -Eo '^[0-9a-f]{6,}' <<<"$current_out" | head -n 1 || true)"
  head_rev="$(alembic heads 2>&1 | grep -Eo '^[0-9a-f]{6,}' | head -n 1 || true)"
  [[ -n "$head_rev" ]] || die "could not read migration heads from $IMAGE"
  if [[ -z "$current_rev" ]]; then
    # Untracked. Only safe to migrate from scratch if it holds no tables at
    # all (a new app's freshly created database); anything else needs the
    # one-time adoption, or migrations would collide with existing tables.
    tables_out="$(docker compose -p "$APP" --project-directory "$SERVICE_DIR" \
        -f "$REPO_DIR/$APP/compose.yml" -f "$candidate" \
        run --rm --no-deps -T "$APP" python -c "$COUNT_TABLES" 2>&1)" \
      || die "couldn't inspect the database (is Postgres up?):
$tables_out"
    tables="$(tail -n 1 <<<"$tables_out" | tr -d '[:space:]')"
    [[ "$tables" == 0 ]] || die "database isn't tracked by Alembic yet and already has tables. Do the one-time adoption in mindless_meals/docs/database.md (Atlas deployment) first. Nothing was changed; ${previous:-nothing} is still running."
    log "Empty database; creating the schema from scratch"
    current_rev="(empty)"
  fi

  # backup.sh connects as the app's own role, taken from DATABASE_URL.
  db_user="$(sed -E 's#^[^:]+://([^:@/]+).*#\1#' <<<"$db_url")"
  db_name="$(sed -E 's#^.*/([^/?]+)(\?.*)?$#\1#' <<<"$db_url")"
  log "Backing up database '$db_name'"
  DB_ROLE="$db_user" BACKUP_DIR="$BACKUP_DIR" "$REPO_DIR/postgres/scripts/backup.sh" "$db_name"

  if [[ "$current_rev" != "$head_rev" ]]; then
    log "Migrating $current_rev -> $head_rev"
    alembic upgrade head || die "migration failed. $previous is still running; latest backup is in $BACKUP_DIR"
  else
    log "No pending migrations ($current_rev)"
  fi

  # Shared Undercurrent identity database (shared/undercurrent-identity),
  # used by every app that has IDENTITY_DATABASE_URL. Back it up, then bring
  # its schema up to date with the NEW image, still before the switch.
  id_url="$(grep -E '^IDENTITY_DATABASE_URL=' "$SERVICE_DIR/.env" | tail -n 1 | cut -d= -f2- | tr -d "\"'" || true)"
  if [[ "$id_url" == postgresql* ]]; then
    id_user="$(sed -E 's#^[^:]+://([^:@/]+).*#\1#' <<<"$id_url")"
    id_name="$(sed -E 's#^.*/([^/?]+)(\?.*)?$#\1#' <<<"$id_url")"
    log "Backing up identity database '$id_name'"
    DB_ROLE="$id_user" BACKUP_DIR="$BACKUP_DIR" "$REPO_DIR/postgres/scripts/backup.sh" "$id_name"
    log "Migrating the identity database"
    docker compose -p "$APP" --project-directory "$SERVICE_DIR" \
        -f "$REPO_DIR/$APP/compose.yml" -f "$candidate" \
        run --rm --no-deps -T "$APP" flask --app app identity migrate \
      || die "identity database migration failed. ${previous:-nothing} is still running; latest backup is in $BACKUP_DIR"
  fi
  rm -f "$candidate"
else
  log "Not on Postgres; skipping backup and migrations"
fi

# --- 3. Switch, 4. revert on failure --------------------------------------
# Only now touch the service dir: the repo-owned compose file, plus
# compose.override.yml (written by switch_to) pinning the image.
cp "$REPO_DIR/$APP/compose.yml" "$SERVICE_DIR/compose.yml"
if switch_to "$IMAGE"; then
  record "$IMAGE" ok
  log "Deployed $IMAGE and it's healthy"
else
  record "$IMAGE" failed
  log "Last logs from $CONTAINER:"; docker logs --tail 40 "$CONTAINER" 2>&1 || true
  if [[ -n "$previous" && "$previous" != "$IMAGE" ]]; then
    log "Reverting to $previous"
    if switch_to "$previous"; then
      log "Reverted to $previous"
    else
      log "Revert ALSO failed; check the service by hand"
    fi
  fi
  die "$IMAGE failed its health check. Note: any database migration it ran is NOT undone (backup in $BACKUP_DIR)."
fi

# --- Keep the last few images for quick rollback ---------------------------
mapfile -t old < <(docker images "$APP" --format '{{.Repository}}:{{.Tag}}' \
  | grep -vxF -e "$IMAGE" -e "${previous:-}" -e "$APP:local" | tail -n +"$((KEEP_IMAGES + 1))")
if ((${#old[@]})); then
  log "Removing old images: ${old[*]}"
  docker rmi "${old[@]}" >/dev/null 2>&1 || true
fi
