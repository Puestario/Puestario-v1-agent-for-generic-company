"""Upload an existing encrypted backup to an explicit client folder. Operator-only."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from .adapters import load_secret
from .backup import retention_candidates
from .control import slug
from .store import DeskError, Store


def list_backups(service, folder_id):
    rows, token = [], None
    while True:
        response = service.files().list(q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken,files(id,name,createdTime,appProperties)", pageSize=1000, pageToken=token).execute()
        rows.extend(response.get("files", []))
        token = response.get("nextPageToken")
        if not token: return rows


def upload(service, archive, company, folder_id, keep_days=14, prune=False):
    from googleapiclient.http import MediaFileUpload
    slug(company)
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", folder_id): raise DeskError("Use an explicit Drive folder ID")
    if archive.suffix != ".age" or archive.is_symlink() or not archive.is_file(): raise DeskError("Choose an encrypted .age archive")
    with archive.open("rb") as handle:
        if not handle.read(32).startswith(b"age-encryption.org/v1\n"): raise DeskError("Archive is not an age encrypted file")
    folder = service.files().get(fileId=folder_id, fields="id,mimeType,trashed,capabilities(canAddChildren)").execute()
    if folder.get("trashed") or folder.get("mimeType") != "application/vnd.google-apps.folder" or not folder.get("capabilities",{}).get("canAddChildren"):
        raise DeskError("The specified backup folder is not writable")
    checksum = hashlib.md5(archive.read_bytes(), usedforsecurity=False).hexdigest()
    name = f"puestario-{company}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{checksum[:8]}.age"
    row = service.files().create(body={"name":name,"parents":[folder_id],"appProperties":{
        "puestarioCompany":company,"puestarioBackup":"age-v1"}},
        media_body=MediaFileUpload(str(archive),mimetype="application/octet-stream",resumable=True),
        fields="id,name,size,md5Checksum").execute()
    if row.get("md5Checksum") != checksum or int(row.get("size",-1)) != archive.stat().st_size:
        raise DeskError("Uploaded file did not verify; older backups were kept")
    candidates = retention_candidates(list_backups(service, folder_id), company, keep_days)
    candidates = [file_id for file_id in candidates if file_id != row["id"]]
    removed = []
    if prune:
        for file_id in candidates:
            service.files().update(fileId=file_id,body={"trashed":True},fields="id,trashed").execute()
            removed.append(file_id)
    return {"uploaded":row["id"],"verified":True,"retention_candidates":candidates,"trashed":removed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--archive",type=Path,required=True)
    parser.add_argument("--folder-id",required=True)
    parser.add_argument("--connection",required=True)
    parser.add_argument("--keep-days",type=int,default=14)
    parser.add_argument("--prune",action="store_true")
    args = parser.parse_args()
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        store = Store(args.root)
        secret = load_secret(store.root, slug(args.connection))
        credentials = Credentials(token=None, refresh_token=secret["refresh_token"],token_uri="https://oauth2.googleapis.com/token",
            client_id=secret["client_id"],client_secret=secret["client_secret"],scopes=["https://www.googleapis.com/auth/drive.file"])
        result = upload(build("drive","v3",credentials=credentials,cache_discovery=False), args.archive,
            store.read()["company"]["company_id"],args.folder_id,args.keep_days,args.prune)
        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps({"ok":False,"error":str(exc) if isinstance(exc,DeskError) else "Drive backup failed; check private local logs"}))
        return 1


if __name__ == "__main__": raise SystemExit(main())
