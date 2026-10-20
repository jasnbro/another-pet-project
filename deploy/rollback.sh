#!/usr/bin/env bash
# Put Mindless Meals back on an earlier image.
#
#   deploy/rollback.sh                 # the version before the current one
#   deploy/rollback.sh <git sha>       # a specific earlier version
#   deploy/rollback.sh --list          # show deploy history
#
# Rolls back CODE only. It does not undo database migrations: if the newer
# version changed the schema, restore from the backup the deploy took
# (postgres/scripts/restore.sh) -- see deploy/README.md.
set -euo pipefail
# shellcheck source=deploy/common.sh
source "$(dirname "$0")/common.sh"

if [[ "${1:-}" == "--list" ]]; then
  [[ -f "$HISTORY" ]] && cat "$HISTORY" || echo "No deploys recorded yet."
  exit 0
fi

take_lock

if [[ -n "${1:-}" ]]; then
  target="$APP:${1:0:12}"
else
  target="$(ok_image 1)"
  [[ -n "$target" ]] || die "no earlier successful deploy recorded to roll back to"
fi

docker image inspect "$target" >/dev/null 2>&1 \
  || die "$target isn't on this machine (only the last few are kept). Redeploy that commit instead: deploy/deploy.sh <sha>"

current="$(running_image)"
log "Rolling back: ${current:-nothing} -> $target"
if switch_to "$target"; then
  record "$target" ok
  log "Now running $target. Database schema was not changed."
else
  record "$target" failed
  docker logs --tail 40 "$CONTAINER" 2>&1 || true
  die "$target is not healthy either; check the service by hand"
fi
