#!/usr/bin/env bash
# Deploy one revision of Mindless Meals on ATLAS.
#
#   deploy/deploy.sh <git sha>
#
# Run from a checkout of that revision (the GitHub Actions runner does this;
# see deploy/README.md). Steps:
#   1. Build mindless_meals:<sha> from this checkout.
#   2. If on Postgres: refuse unless the database is under Alembic, back it
#      up, then apply any pending migrations with the NEW image.
#   3. Switch the container to the new image and wait for its health check.
#   4. If it isn't healthy, switch back to the previous image and fail.
#
# Never touches other services, ./data, or .env. Safe to re-run.
#
# Env overrides: SERVICE_DIR (default ~/services/mindless_meals),
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

take_lock
log "Deploying $IMAGE to $SERVICE_DIR"

# --- Preflight: fail before changing anything ---------------------------
[[ -f "$SERVICE_DIR/.env" ]] || die "$SERVICE_DIR/.env not found (it holds DATABASE_URL and is never in git)"
for net in atlas-proxy postgres_default; do
  docker network inspect "$net" >/dev/null 2>&1 || die "Docker network '$net' is missing"
done

# --- 1. Build ------------------------------------------------------------
docker build --label "org.opencontainers.image.revision=$SHA" -t "$IMAGE" "$REPO_DIR/$APP"

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
  [[ -n "$current_rev" ]] || die "database isn't tracked by Alembic yet. Do the one-time adoption in mindless_meals/docs/database.md (Atlas deployment) first. Nothing was changed; $previous is still running."

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
