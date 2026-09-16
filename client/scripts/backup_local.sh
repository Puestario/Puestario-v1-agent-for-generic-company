#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  WARNING — READ BEFORE ENABLING
#
#  This script archives the ENTIRE OpenClaw home, INCLUDING:
#      credentials/   — live API credentials
#      secrets/       — live secret files
#      workspace/     — including any file holding keys in plain text
#
#  The archive is NOT encrypted. Anyone who can read the destination can read
#  every credential this agent holds.
#
#  Do not enable until you have decided where the archive lands, who can read
#  it, and how long it is kept. This is why the script lives in client/ and
#  not in core/ — it is a per-install decision, not a default.
# ═══════════════════════════════════════════════════════════════════════════
# Nightly OpenClaw backup — local archive with retention
# Run: bash /path/to/scripts/backup_local.sh
# Configure: set OPENCLAW_HOME and BACKUP_DIR below or via env vars

set -euo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/agent}"
KEEP_DAYS="${KEEP_DAYS:-14}"

case "${KEEP_DAYS}" in
  ''|*[!0-9]*) echo "KEEP_DAYS must be a nonnegative integer" >&2; exit 1 ;;
esac
mkdir -p "${BACKUP_DIR}"
OPENCLAW_HOME=$(cd "${OPENCLAW_HOME}" && pwd -P)
BACKUP_DIR=$(cd "${BACKUP_DIR}" && pwd -P)
case "${BACKUP_DIR}/" in
  "${OPENCLAW_HOME}/"*) echo "BACKUP_DIR must be outside OPENCLAW_HOME" >&2; exit 1 ;;
esac
# Build privately in the destination filesystem; publish only a validated archive.
STAGING_DIR=$(mktemp -d "${BACKUP_DIR}/.agent-backup.XXXXXX")
ARCHIVE="${STAGING_DIR}/archive.tar.gz"
trap 'rm -f "${ARCHIVE}"; rmdir "${STAGING_DIR}"' EXIT
trap 'exit 1' HUP INT TERM
TIMESTAMP=$(date -u +"%Y-%m-%d_%H%M%S")
FILENAME="agent-backup-${TIMESTAMP}-${STAGING_DIR##*.}.tar.gz"
DEST="${BACKUP_DIR}/${FILENAME}"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting backup: ${FILENAME}"

tar -czf "${ARCHIVE}" -C "${OPENCLAW_HOME}" \
  --exclude="*.DS_Store" \
  openclaw.json workspace state credentials secrets agents

gzip -t "${ARCHIVE}"
tar -tzf "${ARCHIVE}" >/dev/null
mv "${ARCHIVE}" "${DEST}"

SIZE=$(du -sh "${DEST}" | cut -f1)
echo "  Archived: ${DEST} (${SIZE})"

PRUNED=$(find "${BACKUP_DIR}" -maxdepth 1 -type f -name "agent-backup-*.tar.gz" -mtime +"${KEEP_DAYS}" -print -delete | wc -l | tr -d ' ')
echo "  Pruned: ${PRUNED} backup(s) older than ${KEEP_DAYS} days"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Done: ${FILENAME} (${SIZE})"
