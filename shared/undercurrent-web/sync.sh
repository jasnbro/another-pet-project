#!/usr/bin/env bash
# Copy the shared Undercurrent web snippet into an app.
#
#   shared/undercurrent-web/sync.sh mindless_meals          # copy
#   shared/undercurrent-web/sync.sh --check mindless_meals  # fail if out of date
#
# Apps are copied into (not symlinked) because each app's container only
# bind-mounts its own ./app folder; a symlink out of it would break there.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"

check=0
if [[ "${1:-}" == "--check" ]]; then check=1; shift; fi
[[ $# -ge 1 ]] || { echo "usage: $0 [--check] <app_dir> [<app_dir>...]" >&2; exit 2; }

status=0
for app in "$@"; do
  app_root="$repo/$app/app"
  [[ -d "$app_root" ]] || { echo "no such app: $app_root" >&2; exit 2; }
  pairs=(
    "install-shortcut.js:static/undercurrent/install-shortcut.js"
    "install-shortcut.css:static/undercurrent/install-shortcut.css"
    "sw.js:static/undercurrent/sw.js"
    "_install_shortcut.html:templates/_install_shortcut.html"
  )
  for pair in "${pairs[@]}"; do
    src="$here/${pair%%:*}"
    dst="$app_root/${pair#*:}"
    if (( check )); then
      if ! cmp -s "$src" "$dst"; then
        echo "out of date: $app/app/${pair#*:} (run shared/undercurrent-web/sync.sh $app)" >&2
        status=1
      fi
    else
      mkdir -p "$(dirname "$dst")"
      cp "$src" "$dst"
      echo "copied ${pair%%:*} -> $app/app/${pair#*:}"
    fi
  done
done
exit $status
