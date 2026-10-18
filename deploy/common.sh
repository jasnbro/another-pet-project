# Shared helpers for deploy.sh and rollback.sh. Sourced, not executed.
# shellcheck shell=bash

APP="${APP:-mindless_meals}"
# shellcheck disable=SC2034  # used by deploy.sh
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="${SERVICE_DIR:-$HOME/services/$APP}"
STATE_DIR="$SERVICE_DIR/.deploy"
HISTORY="$STATE_DIR/history"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-90}"
CONTAINER="${CONTAINER:-$APP}"

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

take_lock() {
  mkdir -p "$STATE_DIR"
  exec 9>"$STATE_DIR/lock"
  flock -n 9 || die "another deploy or rollback is already running"
}

# Run compose in the service dir, so .env, ./data and compose.override.yml
# resolve exactly as they do for a manual `docker compose ...` there.
compose() { (cd "$SERVICE_DIR" && docker compose -p "$APP" "$@"); }

# Pin the running image. compose.override.yml is auto-loaded by compose,
# so manual commands in the service dir keep using the deployed version.
pin_image() {
  cat > "$SERVICE_DIR/compose.override.yml" <<EOF
# Written by deploy/ -- the image currently deployed. Don't edit by hand;
# use deploy/rollback.sh to change it.
services:
  $APP:
    image: $1
EOF
}

running_image() {
  docker inspect -f '{{.Config.Image}}' "$CONTAINER" 2>/dev/null || true
}

wait_healthy() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT)) status
  while (( SECONDS < deadline )); do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$CONTAINER" 2>/dev/null || echo missing)"
    case "$status" in
      healthy) return 0 ;;
      unhealthy|exited|dead|missing) log "container status: $status"; [[ "$status" == unhealthy ]] && return 1 ;;
    esac
    sleep 3
  done
  log "not healthy after ${HEALTH_TIMEOUT}s (last status: ${status:-unknown})"
  return 1
}

switch_to() {
  local image="$1"
  pin_image "$image"
  compose up -d --no-build --remove-orphans "$APP"
  wait_healthy
}

record() { printf '%s %s %s\n' "$(date -u +%FT%TZ)" "$1" "$2" >> "$HISTORY"; }

# Last image recorded as successfully deployed ("ok"), optionally skipping
# the most recent N ok entries (1 = the one before the current version).
ok_image() {
  local skip="${1:-0}"
  [[ -f "$HISTORY" ]] || return 0
  awk -v skip="$skip" '$3 == "ok" {ok[n++] = $2} END {if (n > skip) print ok[n - 1 - skip]}' "$HISTORY"
}
