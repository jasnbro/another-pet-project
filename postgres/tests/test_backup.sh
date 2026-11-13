#!/usr/bin/env bash
# Tests for postgres/scripts/{backup,nightly_backup,restore}.sh against a
# fake docker and a fake mountpoint (no Postgres needed). Requires `age`.
#   bash postgres/tests/test_backup.sh
# restore_test.sh needs a real Postgres; see postgres/README.md#backups for
# how it was verified.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
scripts="$here/../scripts"
pass=0; fail=0

command -v age >/dev/null || { echo "age is required (sudo apt install age)"; exit 1; }

setup() {
  T="$(mktemp -d)"
  mkdir -p "$T/bin" "$T/ssd"
  ln -s "$here/fake-docker" "$T/bin/docker"
  ln -s "$here/fake-mountpoint" "$T/bin/mountpoint"
  age-keygen -o "$T/key.txt" 2>/dev/null
  export PATH="$T/bin:$PATH" POSTGRES_USER=madamada FAKE_DUMP_FAIL="" FAKE_MOUNTS="$T/ssd"
  RECIPIENT="$(age-keygen -y "$T/key.txt")"
  unset BACKUP_AGE_RECIPIENT BACKUP_REQUIRE_MOUNT BACKUP_DIR BACKUP_AGE_IDENTITY BACKUP_AGE_IDENTITY_FILE
}
check() { # name, condition...
  local name="$1"; shift
  if "$@"; then pass=$((pass + 1)); echo "ok   - $name"; else fail=$((fail + 1)); echo "FAIL - $name"; fi
}
quiet() { "$@" >"$T/out" 2>&1; }
count() { find "$1" -type f -name "$2" 2>/dev/null | wc -l; }

# 1. Plain backup (what deploy.sh uses) is unchanged
setup
quiet env BACKUP_DIR="$T/plain" "$scripts/backup.sh"; rc=$?
check "plain: exits 0" test $rc -eq 0
check "plain: defaults to mindless_meals" test "$(count "$T/plain" 'mindless_meals_*.sql.gz')" -eq 1
check "plain: readable dump" bash -c "zcat '$T'/plain/*.sql.gz | grep -q 'fake dump of mindless_meals'"

# 2. Retention deletes old dumps of this DB only, not a prefix-sharing DB
setup; mkdir -p "$T/r"
touch -d '20 days ago' "$T/r/mindless_meals_20200101T000000Z.sql.gz" "$T/r/mindless_meals_20200101T000000Z.sql.gz.age" \
  "$T/r/mindless_meals_restored_20200101T000000Z.sql.gz"
quiet env BACKUP_DIR="$T/r" "$scripts/backup.sh" mindless_meals
check "retention: old plain + encrypted dumps removed" test ! -e "$T/r/mindless_meals_20200101T000000Z.sql.gz" -a ! -e "$T/r/mindless_meals_20200101T000000Z.sql.gz.age"
check "retention: other database's dump kept" test -e "$T/r/mindless_meals_restored_20200101T000000Z.sql.gz"

# 3. Encryption
setup
quiet env BACKUP_DIR="$T/e" BACKUP_AGE_RECIPIENT="$RECIPIENT" "$scripts/backup.sh" mindless_meals; rc=$?
check "encrypted: exits 0" test $rc -eq 0
check "encrypted: writes .sql.gz.age only" test "$(count "$T/e" '*.age')" -eq 1 -a "$(count "$T/e" '*.sql.gz')" -eq 0
check "encrypted: file is age ciphertext, not gzip" bash -c "head -c 21 '$T'/e/*.age | grep -qx 'age-encryption.org/v1'"
check "encrypted: decrypts with the private key" bash -c "age -d -i '$T/key.txt' '$T'/e/*.age | zcat | grep -q 'dump complete'"
quiet env BACKUP_DIR="$T/e2" BACKUP_AGE_RECIPIENT="not-a-key" "$scripts/backup.sh"; rc=$?
check "encrypted: bad recipient refused" test $rc -ne 0 -a ! -d "$T/e2"

# 4. Several databases; one failing doesn't stop the others, and is loud
setup; export FAKE_DUMP_FAIL="capacity"
quiet env BACKUP_DIR="$T/m" BACKUP_AGE_RECIPIENT="$RECIPIENT" "$scripts/backup.sh" capacity mindless_meals; rc=$?
check "multi: exits non-zero when one fails" test $rc -ne 0
check "multi: names the failed database" grep -q "failed: capacity" "$T/out"
check "multi: other database still backed up" test "$(count "$T/m" 'mindless_meals_*.age')" -eq 1
check "multi: failed dump leaves no file" test "$(count "$T/m" 'capacity_*')" -eq 0

# 5. Mount guard
setup
quiet env BACKUP_DIR="$T/ssd/pg" BACKUP_REQUIRE_MOUNT="$T/ssd" "$scripts/backup.sh"; rc=$?
check "mount: mounted -> exits 0" test $rc -eq 0 -a "$(count "$T/ssd/pg" '*.sql.gz')" -eq 1
setup; export FAKE_MOUNTS=""
quiet env BACKUP_DIR="$T/ssd/pg" BACKUP_REQUIRE_MOUNT="$T/ssd" "$scripts/backup.sh"; rc=$?
check "mount: unmounted -> refuses" test $rc -ne 0
check "mount: unmounted -> writes nothing" test ! -e "$T/ssd/pg"
check "mount: unmounted -> says why" grep -q "not a mounted filesystem" "$T/out"
setup
quiet env BACKUP_DIR="$T/ssd/../main-disk" BACKUP_REQUIRE_MOUNT="$T/ssd" "$scripts/backup.sh"; rc=$?
check "mount: dir outside mount refused" test $rc -ne 0 -a ! -e "$T/main-disk"
setup; mkdir "$T/main-disk"; ln -s "$T/main-disk" "$T/ssd/link"
quiet env BACKUP_DIR="$T/ssd/link" BACKUP_REQUIRE_MOUNT="$T/ssd" "$scripts/backup.sh"; rc=$?
check "mount: symlink out of the mount refused" test $rc -ne 0 -a -z "$(ls -A "$T/main-disk")"

# 6. Nightly wrapper
setup
quiet env BACKUP_DIR="$T/ssd/pg" BACKUP_REQUIRE_MOUNT="$T/ssd" "$scripts/nightly_backup.sh" mindless_meals; rc=$?
check "nightly: refuses without encryption" test $rc -ne 0 -a ! -e "$T/ssd/pg"
quiet env BACKUP_DIR="$T/pg" BACKUP_AGE_RECIPIENT="$RECIPIENT" "$scripts/nightly_backup.sh" mindless_meals; rc=$?
check "nightly: refuses without mount guard" test $rc -ne 0 -a ! -e "$T/pg"
quiet env BACKUP_DIR="$T/ssd/pg" BACKUP_REQUIRE_MOUNT="$T/ssd" BACKUP_AGE_RECIPIENT="$RECIPIENT" "$scripts/nightly_backup.sh"; rc=$?
check "nightly: refuses with no databases named" test $rc -ne 0
quiet env BACKUP_DIR="$T/ssd/pg" BACKUP_REQUIRE_MOUNT="$T/ssd" BACKUP_AGE_RECIPIENT="$RECIPIENT" "$scripts/nightly_backup.sh" mindless_meals capacity; rc=$?
check "nightly: success exits 0" test $rc -eq 0 -a "$(count "$T/ssd/pg" '*.age')" -eq 2
check "nightly: success records .last_success" test -f "$T/ssd/pg/.last_success"
setup; export FAKE_DUMP_FAIL="capacity"
quiet env BACKUP_DIR="$T/ssd/pg" BACKUP_REQUIRE_MOUNT="$T/ssd" BACKUP_AGE_RECIPIENT="$RECIPIENT" "$scripts/nightly_backup.sh" mindless_meals capacity; rc=$?
check "nightly: failure exits non-zero" test $rc -ne 0
check "nightly: failure doesn't record .last_success" test ! -e "$T/ssd/pg/.last_success"

# 7. Restore input handling
setup
quiet env BACKUP_DIR="$T/x" BACKUP_AGE_RECIPIENT="$RECIPIENT" "$scripts/backup.sh"
enc="$(ls "$T"/x/*.age)"
quiet "$scripts/restore.sh" "$enc" scratch; rc=$?
check "restore: encrypted without a key refused" test $rc -ne 0 -a "$(grep -c BACKUP_AGE_IDENTITY "$T/out")" -ge 1
quiet env BACKUP_AGE_IDENTITY="$(grep AGE-SECRET "$T/key.txt")" "$scripts/restore.sh" "$enc" scratch; rc=$?
check "restore: key from environment works" test $rc -eq 0
quiet env BACKUP_AGE_IDENTITY_FILE="$T/key.txt" "$scripts/restore.sh" "$enc" scratch; rc=$?
check "restore: key file works" test $rc -eq 0
age-keygen -o "$T/wrong.txt" 2>/dev/null
quiet env BACKUP_AGE_IDENTITY_FILE="$T/wrong.txt" "$scripts/restore.sh" "$enc" scratch; rc=$?
check "restore: wrong key fails" test $rc -ne 0
touch "$T/x/notes.txt"
quiet "$scripts/restore.sh" "$T/x/notes.txt" scratch; rc=$?
check "restore: unknown file type refused" test $rc -ne 0

echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
