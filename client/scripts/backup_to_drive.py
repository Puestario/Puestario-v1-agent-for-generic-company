#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════
 WARNING — READ BEFORE ENABLING

 This script archives the ENTIRE OpenClaw home, INCLUDING:
     credentials/   — live API credentials
     secrets/       — live secret files
     workspace/     — including any file holding keys in plain text

 It then UPLOADS that archive TO GOOGLE DRIVE, UNENCRYPTED, into a folder
 whose default name is the same on every install.

 That means every credential this agent holds leaves the machine and lands in
 a Drive account. Whose account, and who else can see that folder, is a
 question you must answer before enabling this.

 Do not enable until you have. This is why the script lives in client/ and not
 in core/ — it is a per-install decision, not a default.
═══════════════════════════════════════════════════════════════════════════
"""
"""
Nightly OpenClaw backup to Google Drive.
Archives critical dirs, uploads timestamped tarball, prunes files older than KEEP_DAYS.

Required env vars (or set paths below):
  OPENCLAW_HOME — path to .openclaw directory (default: $HOME/.openclaw)
  OAUTH_FILE    — path to google-oauth.json
  TOKEN_FILE    — path to google-token.json
  DRIVE_FOLDER_NAME — name of Drive folder to upload to (default: Agent-Backups)
  KEEP_DAYS     — days of backups to retain (default: 14)
"""

import json
import os
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

OPENCLAW_HOME = Path(os.environ.get("OPENCLAW_HOME", Path.home() / ".openclaw"))
SECRETS_DIR = OPENCLAW_HOME / "secrets"
OAUTH_FILE = Path(os.environ.get("OAUTH_FILE", SECRETS_DIR / "google-oauth.json"))
TOKEN_FILE = Path(os.environ.get("TOKEN_FILE", SECRETS_DIR / "google-token.json"))

BACKUP_DIRS = [
    str(OPENCLAW_HOME / "openclaw.json"),
    str(OPENCLAW_HOME / "workspace"),
    str(OPENCLAW_HOME / "state"),
    str(OPENCLAW_HOME / "credentials"),
    str(OPENCLAW_HOME / "secrets"),
    str(OPENCLAW_HOME / "agents"),
]

DRIVE_FOLDER_NAME = os.environ.get("DRIVE_FOLDER_NAME", "Agent-Backups")
KEEP_DAYS = int(os.environ.get("KEEP_DAYS", "14"))


def get_drive_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    with open(OAUTH_FILE) as f:
        oauth = json.load(f)
    creds_data = oauth.get("installed", oauth.get("web", {}))

    with open(TOKEN_FILE) as f:
        token = json.load(f)

    creds = Credentials(
        token=token.get("access_token"),
        refresh_token=token.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=creds_data["client_id"],
        client_secret=creds_data["client_secret"],
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )

    if creds.expired or not creds.valid:
        creds.refresh(Request())
        token["access_token"] = creds.token
        with open(TOKEN_FILE, "w") as f:
            json.dump(token, f)

    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, name):
    res = service.files().list(
        q=f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)",
    ).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]


def prune_old_backups(service, folder_id, keep_days):
    from datetime import timedelta
    from googleapiclient.errors import HttpError

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    res = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, createdTime)",
        orderBy="createdTime",
    ).execute()
    removed = 0
    for f in res.get("files", []):
        created = datetime.fromisoformat(f["createdTime"].replace("Z", "+00:00"))
        if created < cutoff:
            try:
                service.files().delete(fileId=f["id"]).execute()
                removed += 1
                print(f"  Pruned: {f['name']}")
            except HttpError as e:
                print(f"  Could not prune {f['name']}: {e}")
    return removed


def create_tarball(paths, dest):
    with tarfile.open(dest, "w:gz") as tar:
        for p in paths:
            path = Path(p)
            if path.exists():
                tar.add(str(path), arcname=path.name if path.is_file() else path.name)
            else:
                print(f"  Warning: {p} not found, skipping")
    return Path(dest).stat().st_size


def upload_file(service, local_path, filename, folder_id):
    from googleapiclient.http import MediaFileUpload

    meta = {"name": filename, "parents": [folder_id]}
    media = MediaFileUpload(local_path, mimetype="application/gzip", resumable=True)
    f = service.files().create(body=meta, media_body=media, fields="id, name, size").execute()
    return f


def main():
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = f"agent-backup-{ts}.tar.gz"

    print(f"[{datetime.now().isoformat()}] Starting backup: {filename}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tarball = os.path.join(tmpdir, filename)

        print("  Creating tarball...")
        size_bytes = create_tarball(BACKUP_DIRS, tarball)
        size_mb = size_bytes / 1024 / 1024
        print(f"  Tarball size: {size_mb:.1f} MB")

        print("  Connecting to Google Drive...")
        service = get_drive_service()

        print(f"  Locating Drive folder '{DRIVE_FOLDER_NAME}'...")
        folder_id = get_or_create_folder(service, DRIVE_FOLDER_NAME)

        print("  Uploading...")
        result = upload_file(service, tarball, filename, folder_id)
        print(f"  Uploaded: {result['name']} ({int(result.get('size', 0)) / 1024 / 1024:.1f} MB)")

        print(f"  Pruning backups older than {KEEP_DAYS} days...")
        removed = prune_old_backups(service, folder_id, KEEP_DAYS)
        print(f"  Pruned {removed} old backup(s)")

    print(f"[{datetime.now().isoformat()}] Backup complete: {filename}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
