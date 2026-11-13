#!/usr/bin/env bash
# The scheduled backup on ATLAS: backup.sh with encryption and the SSD mount
# guard made mandatory. Refuses to run if either is missing, so a
# misconfigured cron job fails loudly instead of quietly writing plain-text
# dumps to the main disk.
#
# Usage (run via Doppler so the settings come from there, not from disk):
#   doppler run --project atlas-backups --config prd -- \
#     ~/services/postgres/scripts/nightly_backup.sh mindless_meals capacity
#
# Required environment:
#   BACKUP_AGE_RECIPIENT   age public key (age1...)
#   BACKUP_REQUIRE_MOUNT   the SSD mount point, e.g. /mnt/backup-ssd
#   BACKUP_DIR             a directory inside it, e.g. /mnt/backup-ssd/postgres
# Optional: everything backup.sh accepts (DB_ROLE, RETENTION_DAYS, ...).
#
# On success, touches $BACKUP_DIR/.last_success so "when did a backup last
# work?" is one `ls -l` away. See postgres/README.md#backups.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

missing=()
for v in BACKUP_AGE_RECIPIENT BACKUP_REQUIRE_MOUNT BACKUP_DIR; do
  [ -n "${!v:-}" ] || missing+=("$v")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "nightly_backup.sh: ERROR: not set: ${missing[*]}. Run it under 'doppler run'. Nothing was written." >&2
  exit 1
fi
[ $# -gt 0 ] || { echo "nightly_backup.sh: ERROR: name the databases to back up." >&2; exit 1; }

echo "== nightly backup $(date -u +%Y-%m-%dT%H:%M:%SZ): $*"
"$SCRIPT_DIR/backup.sh" "$@"
touch "$BACKUP_DIR/.last_success"
