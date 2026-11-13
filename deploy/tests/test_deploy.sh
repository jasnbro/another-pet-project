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
  export DOPPLER="$T/bin/doppler" FAKE_DOPPLER_FAIL="" UC_SETTINGS=""
  export PATH="$T/bin:$PATH" FAKE_DIR="$T/fake" SERVICE_DIR="$T/svc" BACKUP_DIR="$T/backups" HEALTH_TIMEOUT=5
  # The calling environment may set these (gym-log.yml sets APP=gym_log for
  # every job); each test starts from the default app unless it sets them.
  unset APP CONTAINER
  export FAKE_CURRENT=aaaa1111 FAKE_HEAD=aaaa1111 FAKE_UNHEALTHY="" FAKE_DB_DOWN="" FAKE_MIGRATE_FAIL="" FAKE_TABLES=3
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

# 3b. Brand-new, empty database (a new app's first deploy) -> migrate from scratch
setup; export FAKE_CURRENT="" FAKE_TABLES=0
quiet "$deploy" 3b3b3b3b3b3b3b3b; rc=$?
check "empty DB deploy exits 0" test $rc -eq 0
check "empty DB: schema created by migrating" test -f "$FAKE_DIR/migrations"
check "empty DB: backed up first" bash -c "ls '$T/backups' | grep -q sql.gz"
check "empty DB: switched to new image" test "$(running)" = mindless_meals:3b3b3b3b3b3b

# 3c. Another app (APP=gym_log) uses its own image, service dir and database
setup; export APP=gym_log CONTAINER=gym_log FAKE_CURRENT="" FAKE_TABLES=0
echo 'DATABASE_URL="postgresql+psycopg2://gym_log_app:secret@postgres:5432/gym_log"' > "$T/svc/.env"
echo 'IDENTITY_DATABASE_URL="postgresql+psycopg2://undercurrent_identity_app:secret@postgres:5432/undercurrent_identity"' >> "$T/svc/.env"
quiet "$deploy" 3c3c3c3c3c3c3c3c; rc=$?
check "gym_log deploy exits 0" test $rc -eq 0
check "gym_log: built its own folder" grep -q 'docker build .* -t gym_log:3c3c3c3c3c3c .*/gym_log$' "$FAKE_DIR/calls"
check "gym_log: backed up its own database" bash -c "ls '$T/backups' | grep -q '^gym_log_.*\.sql\.gz$'"
check "gym_log: backup used its own role" grep -q 'pg_dump -U gym_log_app' "$FAKE_DIR/calls"
check "gym_log: image pinned" grep -q 'image: gym_log:3c3c3c3c3c3c' "$T/svc/compose.override.yml"
unset APP CONTAINER

# 3d. Identity database: backed up and migrated with the new image, before the switch
setup
echo 'IDENTITY_DATABASE_URL=postgresql+psycopg2://undercurrent_identity_app:s3cret@postgres:5432/undercurrent_identity' >> "$T/svc/.env"
quiet "$deploy" 3d3d3d3d3d3d3d3d; rc=$?
check "identity: deploy exits 0" test $rc -eq 0
check "identity: migrated" grep -q identity-migrate "$FAKE_DIR/migrations"
check "identity: backed up with its own role" grep -q 'pg_dump -U undercurrent_identity_app' "$FAKE_DIR/calls"
check "identity: backup file written" bash -c "ls '$T/backups' | grep -q '^undercurrent_identity_.*\.sql\.gz$'"
check "identity: migrated before the switch" bash -c "grep -n 'identity migrate\| up ' '$FAKE_DIR/calls' | head -1 | grep -q 'identity migrate'"
check "identity: password never logged" bash -c "! grep -q s3cret '$T/out'"

# 3e. Identity migration fails -> old version keeps running, service dir untouched
setup; export FAKE_IDENTITY_FAIL=1
echo 'IDENTITY_DATABASE_URL=postgresql+psycopg2://u:p@postgres:5432/undercurrent_identity' >> "$T/svc/.env"
quiet "$deploy" 3e3e3e3e3e3e3e3e; rc=$?
check "identity fail: exits non-zero" test $rc -ne 0
check "identity fail: says so" grep -q "identity database migration failed" "$T/out"
check "identity fail: old version still running" test "$(running)" = mindless_meals_old:latest
check "identity fail: service dir untouched" test ! -f "$T/svc/compose.override.yml"
export FAKE_IDENTITY_FAIL=""

# 3g. An app with sign-in but no IDENTITY_DATABASE_URL -> refuse before building
setup; export APP=gym_log CONTAINER=gym_log
echo 'DATABASE_URL="postgresql+psycopg2://gym_log_app:secret@postgres:5432/gym_log"' > "$T/svc/.env"
quiet "$deploy" 3g3g3g3g3g3g3g3g; rc=$?
if [[ -d "$here/../../gym_log/app/undercurrent_identity" ]]; then
  check "sign-in app without identity db: refused" test $rc -ne 0
  check "sign-in app without identity db: says what to set" grep -q "set IDENTITY_DATABASE_URL" "$T/out"
  check "sign-in app without identity db: nothing built" bash -c "! grep -qs 'docker build' '$FAKE_DIR/calls'"
fi
unset APP CONTAINER

# 3f. No IDENTITY_DATABASE_URL -> identity untouched
setup
quiet "$deploy" 3f3f3f3f3f3f3f3f
check "no identity url: identity not migrated" bash -c "! grep -qs identity-migrate '$FAKE_DIR/migrations'"

# 3h. No .env: settings come from Doppler (project = app name with dashes)
setup; rm "$T/svc/.env"; ln -s "$here/fake-doppler" "$T/bin/doppler"
cat > "$FAKE_DIR/doppler-mindless-meals-prd.env" <<'ENV'
DATABASE_URL=postgresql+psycopg2://mm_app:fromdoppler@postgres:5432/mindless_meals
ENV
quiet "$deploy" 3h3h3h3h3h3h3h3h; rc=$?
check "doppler: deploy exits 0" test $rc -eq 0
check "doppler: ran under the app's project and prd config" grep -q 'doppler run --project mindless-meals --config prd' "$FAKE_DIR/calls"
check "doppler: says where settings came from" grep -q "Settings: Doppler project 'mindless-meals'" "$T/out"
check "doppler: backup used the role from Doppler's DATABASE_URL" grep -q 'pg_dump -U mm_app' "$FAKE_DIR/calls"
check "doppler: migrated and switched" test "$(running)" = mindless_meals:3h3h3h3h3h3h
check "doppler: no .env written to the service dir" test ! -e "$T/svc/.env"
check "doppler: password never logged" bash -c "! grep -q fromdoppler '$T/out'"
quiet "$rollback" --list; quiet "$rollback" 3h3h3h3h3h3h; rc=$?
check "doppler: rollback works too" test $rc -eq 0

# 3i. Doppler fails (not logged in / no project) -> nothing changes
setup; rm "$T/svc/.env"; ln -s "$here/fake-doppler" "$T/bin/doppler"; export FAKE_DOPPLER_FAIL=1
quiet "$deploy" 3i3i3i3i3i3i3i3i; rc=$?
check "doppler fail: exits non-zero" test $rc -ne 0
check "doppler fail: nothing built" bash -c "! grep -qs 'docker build' '$FAKE_DIR/calls'"
check "doppler fail: old version still running" test "$(running)" = mindless_meals_old:latest
export FAKE_DOPPLER_FAIL=""

# 3j. A .env present -> Doppler is never consulted
setup; ln -s "$here/fake-doppler" "$T/bin/doppler"
quiet "$deploy" 3j3j3j3j3j3j3j3j
check ".env present: Doppler not used" bash -c "! grep -qs 'doppler run' '$FAKE_DIR/calls'"

# 3k. Gym Log identity check reads Doppler settings too
setup; rm "$T/svc/.env"; ln -s "$here/fake-doppler" "$T/bin/doppler"; export APP=gym_log CONTAINER=gym_log
printf 'DATABASE_URL=postgresql+psycopg2://gym_log_app:p@postgres:5432/gym_log\n' > "$FAKE_DIR/doppler-gym-log-prd.env"
quiet "$deploy" 3k3k3k3k3k3k3k3k; rc=$?
if [[ -d "$here/../../gym_log/app/undercurrent_identity" ]]; then
  check "doppler + sign-in app without identity db: refused" test $rc -ne 0 -a "$(grep -c 'set IDENTITY_DATABASE_URL' "$T/out")" -ge 1
fi
printf 'IDENTITY_DATABASE_URL=postgresql+psycopg2://undercurrent_identity_app:p@postgres:5432/undercurrent_identity\n' >> "$FAKE_DIR/doppler-gym-log-prd.env"
quiet "$deploy" 3k3k3k3k3k3k3k3l; rc=$?
check "doppler + identity settings: deploys and migrates identity" test $rc -eq 0 -a "$(grep -c identity-migrate "$FAKE_DIR/migrations")" -ge 1
unset APP CONTAINER

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
check "missing .env, no Doppler: refuses" test $rc -ne 0
check "missing .env, no Doppler: says what to do" grep -q "Doppler CLI isn't installed" "$T/out"
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
