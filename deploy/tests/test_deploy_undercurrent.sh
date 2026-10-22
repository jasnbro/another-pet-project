#!/usr/bin/env bash
# Tests for deploy-undercurrent.sh (and rollback.sh with APP=undercurrent)
# against a fake docker (tests/fake-docker).
#   bash deploy/tests/test_deploy_undercurrent.sh
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
deploy="$here/../deploy-undercurrent.sh"; rollback="$here/../rollback.sh"
pass=0; fail=0

setup() {
  T="$(mktemp -d)"
  mkdir -p "$T/bin" "$T/fake" "$T/svc"
  ln -s "$here/fake-docker" "$T/bin/docker"
  export PATH="$T/bin:$PATH" FAKE_DIR="$T/fake" SERVICE_DIR="$T/svc" HEALTH_TIMEOUT=5 FAKE_UNHEALTHY=""
  unset KEEP_IMAGES
}
running() { cat "$FAKE_DIR/running" 2>/dev/null; }
check() { # name, condition...
  local name="$1"; shift
  if "$@"; then pass=$((pass + 1)); echo "ok   - $name"; else fail=$((fail + 1)); echo "FAIL - $name"; fi
}
quiet() { "$@" >"$T/out" 2>&1; }

# 1. First deploy: no .env, no database, nothing running yet
setup
quiet "$deploy" 1111111111111111aaaa; rc=$?
check "first deploy exits 0" test $rc -eq 0
check "runs the new image" test "$(running)" = undercurrent:111111111111
check "builds the undercurrent folder" grep -q 'docker build .*undercurrent:111111111111 .*/undercurrent$' "$FAKE_DIR/calls"
check "compose.yml copied to service dir" test -f "$T/svc/compose.yml"
check "image pinned in override" grep -q 'image: undercurrent:111111111111' "$T/svc/compose.override.yml"
check "recorded ok in history" grep -q 'undercurrent:111111111111 ok' "$T/svc/.deploy/history"
check "no database work" bash -c "! grep -qE 'alembic|pg_dump' '$FAKE_DIR/calls'"

# 2. Unhealthy new version -> automatic revert
setup
quiet "$deploy" 2222222222222222
export FAKE_UNHEALTHY="undercurrent:333333333333"
quiet "$deploy" 3333333333333333; rc=$?
check "unhealthy deploy exits non-zero" test $rc -ne 0
check "unhealthy deploy reverted to previous" test "$(running)" = undercurrent:222222222222
check "unhealthy deploy recorded as failed" grep -q '333333333333 failed' "$T/svc/.deploy/history"

# 3. Rollback reuses rollback.sh with APP=undercurrent
setup
quiet "$deploy" aaaaaaaaaaaa1; quiet "$deploy" bbbbbbbbbbbb2
APP=undercurrent CONTAINER=undercurrent quiet "$rollback"; rc=$?
check "rollback exits 0" test $rc -eq 0
check "rollback went to the previous version" test "$(running)" = undercurrent:aaaaaaaaaaaa

# 4. Only the last few images are kept
setup; export KEEP_IMAGES=3
for i in 1 2 3 4 5 6 7; do quiet "$deploy" "${i}00000000000"; done
kept="$(grep -c '^undercurrent:' "$FAKE_DIR/images")"
check "old images pruned (kept $kept)" test "$kept" -le 5
check "current image kept" grep -qx 'undercurrent:700000000000' "$FAKE_DIR/images"

echo; echo "$pass passed, $fail failed"
((fail == 0))
