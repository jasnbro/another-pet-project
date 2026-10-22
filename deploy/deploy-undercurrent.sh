#!/usr/bin/env bash
# Deploy one revision of the Undercurrent site on ATLAS.
#
#   deploy/deploy-undercurrent.sh <git sha>
#
# Run from a checkout of that revision (the GitHub Actions runner does this;
# see deploy/README.md). The site is static: no .env, no database. Steps:
#   1. Build undercurrent:<sha> from this checkout (the image build runs the
#      site's tests and content validation, so a bad commit fails here).
#   2. Switch the container to the new image and wait for its health check.
#   3. If it isn't healthy, switch back to the previous image and fail.
#
# Roll back with: APP=undercurrent deploy/rollback.sh [sha]
#
# Env overrides: SERVICE_DIR (default ~/services/undercurrent),
# HEALTH_TIMEOUT (default 90s), KEEP_IMAGES (default 5).
set -euo pipefail
export APP=undercurrent CONTAINER=undercurrent
# shellcheck source=deploy/common.sh
source "$(dirname "$0")/common.sh"

SHA="${1:?usage: deploy-undercurrent.sh <git sha>}"
TAG="${SHA:0:12}"
IMAGE="$APP:$TAG"
KEEP_IMAGES="${KEEP_IMAGES:-5}"

take_lock
log "Deploying $IMAGE to $SERVICE_DIR"

# --- Preflight: fail before changing anything ---------------------------
# cloudflared reaches the site by service name over this network.
docker network inspect atlas-proxy >/dev/null 2>&1 || die "Docker network 'atlas-proxy' is missing"

# --- 1. Build ------------------------------------------------------------
docker build --pull --label "org.opencontainers.image.revision=$SHA" -t "$IMAGE" "$REPO_DIR/$APP"

previous="$(running_image)"
log "Currently running: ${previous:-nothing}"

# --- 2. Switch, 3. revert on failure --------------------------------------
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
  die "$IMAGE failed its health check"
fi

# --- Keep the last few images for quick rollback ---------------------------
mapfile -t old < <(docker images "$APP" --format '{{.Repository}}:{{.Tag}}' \
  | grep -vxF -e "$IMAGE" -e "${previous:-}" -e "$APP:local" | tail -n +"$((KEEP_IMAGES + 1))")
if ((${#old[@]})); then
  log "Removing old images: ${old[*]}"
  docker rmi "${old[@]}" >/dev/null 2>&1 || true
fi
