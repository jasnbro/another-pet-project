#!/usr/bin/env bash
# Tests for deploy.sh / rollback.sh against a fake docker (tests/fake-docker).
#   bash deploy/tests/test_deploy.sh
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
deploy="$here/../deploy.sh"; rollback="$here/../rollback.sh"
pass=0; fail=0

setup() {
  T="$(mktemp -d)"
  mkdir -p "$T/bin" "$T/fake" "$T/svc" "$T/backups"
  ln -s "$here/fake-docker" "$T/bin/docker"
  export PATH="$T/bin:$PATH" FAKE_DIR="$T/fake" SERVICE_DIR="$T/svc" BACKUP_DIR="$T/backups" HEALTH_TIMEOUT=5
  export FAKE_CURRENT=aaaa1111 FAKE_HEAD=aaaa1111 FAKE_UNHEALTHY="" FAKE_DB_DOWN="" FAKE_MIGRATE_FAIL=""
  echo 'DATABASE_URL="postgresql+psycopg2://mm_app:secret@postgres:5432/mindless_meals"' > "$T/svc/.env"
  echo "mindless_meals_old:latest" > "$T/fake/running"
}
running() { cat "$FAKE_DIR/running"; }
check() { # name, condition...
  local name="$1"; shift
  if "$@"; then pass=$((pass + 1)); echo "ok   - $name"; else fail=$((fail + 1)); echo "FAIL - $name"; fi
}
quiet() { "$@" >"$T/out" 2>&1; }

# 1. Happy path with a pending migration
setup; export FAKE_HEAD=bbbb2222
quiet "$deploy" 1111111111111111aaaa; rc=$?
check "happy path exits 0" test $rc -eq 0
check "switched to new image" test "$(running)" = mindless_meals:111111111111
check "backup written before migrating" bash -c "ls '$T/backups' | grep -q '^mindless_meals_.*\.sql\.gz$'"
check "backup used the app's own role" grep -q 'pg_dump -U mm_app' "$FAKE_DIR/calls"
check "migration applied" test -f "$FAKE_DIR/migrations"
check "recorded ok in history" grep -q 'mindless_meals:111111111111 ok' "$T/svc/.deploy/history"
check "compose.yml copied to service dir" test -f "$T/svc/compose.yml"
check "image pinned in override" grep -q 'image: mindless_meals:111111111111' "$T/svc/compose.override.yml"

# 2. No pending migration -> backup still taken, no upgrade
setup
quiet "$deploy" 2222222222222222; rc=$?
check "no-migration deploy exits 0" test $rc -eq 0
check "no upgrade when up to date" test ! -f "$FAKE_DIR/migrations"
check "still backed up" bash -c "ls '$T/backups' | grep -q sql.gz"

# 3. Database not yet adopted into Alembic -> refuse, change nothing
setup; export FAKE_CURRENT=""
quiet "$deploy" 3333333333333333; rc=$?
check "untracked DB refuses" test $rc -ne 0
check "untracked DB: old version still running" test "$(running)" = mindless_meals_old:latest
check "untracked DB: no backup/migration" test ! -f "$FAKE_DIR/migrations"
check "untracked DB: explains next step" grep -q "one-time adoption" "$T/out"
check "untracked DB: service dir untouched" test ! -f "$T/svc/compose.yml" -a ! -f "$T/svc/compose.override.yml"

# 4. Database unreachable -> clear error, nothing changed
setup; export FAKE_DB_DOWN=1
quiet "$deploy" 4444444444444444; rc=$?
check "db down refuses" test $rc -ne 0
check "db down: says it couldn't check" grep -q "couldn't check" "$T/out"
check "db down: old version still running" test "$(running)" = mindless_meals_old:latest
check "db down: service dir untouched" test ! -f "$T/svc/compose.yml"

# 5. Migration fails -> old version keeps running
setup; export FAKE_HEAD=bbbb2222 FAKE_MIGRATE_FAIL=1
quiet "$deploy" 5555555555555555; rc=$?
check "failed migration exits non-zero" test $rc -ne 0
check "failed migration: old version still running" test "$(running)" = mindless_meals_old:latest
check "failed migration: service dir untouched" test ! -f "$T/svc/compose.override.yml"

# 6. New version unhealthy -> automatic revert
setup
quiet "$deploy" 6666666666666666
export FAKE_UNHEALTHY="mindless_meals:777777777777"
quiet "$deploy" 7777777777777777; rc=$?
check "unhealthy deploy exits non-zero" test $rc -ne 0
check "unhealthy deploy reverted to previous" test "$(running)" = mindless_meals:666666666666
check "unhealthy deploy recorded as failed" grep -q '777777777777 failed' "$T/svc/.deploy/history"
check "unhealthy deploy warns migrations aren't undone" grep -q "NOT undone" "$T/out"

# 7. Rollback to the previous good version, and to a named one
setup
quiet "$deploy" aaaaaaaaaaaa1; quiet "$deploy" bbbbbbbbbbbb2; quiet "$deploy" cccccccccccc3
quiet "$rollback"; rc=$?
check "rollback exits 0" test $rc -eq 0
check "rollback went to the previous version" test "$(running)" = mindless_meals:bbbbbbbbbbbb
quiet "$rollback" aaaaaaaaaaaa; rc=$?
check "rollback to a named version" test "$(running)" = mindless_meals:aaaaaaaaaaaa
quiet "$rollback" dddddddddddd; rc=$?
check "rollback to an unknown version refuses" test $rc -ne 0
check "unknown rollback leaves service alone" test "$(running)" = mindless_meals:aaaaaaaaaaaa
quiet "$rollback" --list
check "--list shows history" grep -q 'cccccccccccc ok' "$T/out"

# 8. SQLite (no DATABASE_URL) -> no backup or migration
setup; : > "$T/svc/.env"
quiet "$deploy" 8888888888888888; rc=$?
check "sqlite deploy exits 0" test $rc -eq 0
check "sqlite deploy skips backup" bash -c "! ls '$T/backups' | grep -q sql.gz"

# 9. Missing .env -> refuse before building
setup; rm "$T/svc/.env"
quiet "$deploy" 9999999999999999; rc=$?
check "missing .env refuses" test $rc -ne 0
check "missing .env: nothing built" bash -c "! grep -qs 'docker build' '$FAKE_DIR/calls'"

# 10. Only the last few images are kept
setup; export KEEP_IMAGES=3
for i in 1 2 3 4 5 6 7; do quiet "$deploy" "${i}00000000000"; done
kept="$(grep -c '^mindless_meals:' "$FAKE_DIR/images")"
check "old images pruned (kept $kept)" test "$kept" -le 5
check "current image kept" grep -qx 'mindless_meals:700000000000' "$FAKE_DIR/images"
unset KEEP_IMAGES

echo; echo "$pass passed, $fail failed"
((fail == 0))
