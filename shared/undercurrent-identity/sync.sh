#!/usr/bin/env bash
# Copy the shared identity package into an app.
#
#   shared/undercurrent-identity/sync.sh gym_log            # copy
#   shared/undercurrent-identity/sync.sh --check gym_log    # fail if out of date
#
# Copied (not symlinked, not a path dependency) so each app's Docker build,
# whose context is the app's own folder, contains it. Lands in
# <app>/app/undercurrent_identity/. Edit the files HERE, then re-run this.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
src="$here/undercurrent_identity"

check=0
if [[ "${1:-}" == "--check" ]]; then check=1; shift; fi
[[ $# -ge 1 ]] || { echo "usage: $0 [--check] <app_dir> [<app_dir>...]" >&2; exit 2; }

status=0
for app in "$@"; do
  dst="$repo/$app/app/undercurrent_identity"
  [[ -d "$repo/$app/app" ]] || { echo "no such app: $repo/$app/app" >&2; exit 2; }
  if (( check )); then
    if ! diff -r -q -x __pycache__ "$src" "$dst" >/dev/null 2>&1; then
      echo "out of date: $app/app/undercurrent_identity (run shared/undercurrent-identity/sync.sh $app)" >&2
      diff -r -q -x __pycache__ "$src" "$dst" >&2 || true
      status=1
    fi
  else
    rm -rf "$dst"
    mkdir -p "$dst"
    (cd "$src" && find . -type d -name __pycache__ -prune -o -type f -print0 | while IFS= read -r -d '' f; do
      mkdir -p "$dst/$(dirname "$f")"; cp "$f" "$dst/$f"; done)
    echo "copied undercurrent_identity -> $app/app/undercurrent_identity"
  fi
done
exit $status
