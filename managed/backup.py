"""Encrypted, offline snapshots of the actual company root; restore pauses all work."""
import hashlib
import io
import json
import os
import secrets
import shutil
import socket
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath
from .runtime import managed_config, workspace_files
from .store import DeskError, Store, atomic_json

INCLUDED = {"control.json", "release-manifest.json", "release", "workspace", "gateway", "secrets", "security", "evidence"}
MAX_RESTORE_BYTES = 2_000_000_000


def safe_name(value):
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in value or path.parts[0] not in INCLUDED | {"snapshot-manifest.json"}:
        raise DeskError("Backup contains an unsafe path")
    return path


def backup(store, recipient, output, check_stopped=True):
    output = Path(output).expanduser().resolve()
    if output.suffix != ".age" or output == store.root or store.root in output.parents or output.exists():
        raise DeskError("Use a new .age file outside the company folder")
    if not recipient.startswith("age1") or len(recipient) < 50:
        raise DeskError("Use an age public encryption recipient; keep its private recovery key elsewhere")
    if check_stopped:
        try: connection = socket.create_connection(("127.0.0.1", store.read()["install"]["port"]), timeout=1)
        except OSError: pass
        else:
            connection.close()
            raise DeskError("Stop this company's gateway before taking a consistent full backup")
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".encrypted-", dir=output.parent)
    process = None
    try:
        with os.fdopen(fd, "wb") as encrypted, store.locked() as state:
            process = subprocess.Popen(["age", "-r", recipient], stdin=subprocess.PIPE, stdout=encrypted, stderr=subprocess.PIPE)
            manifest = {"company_id": state["company"]["company_id"], "at": time.time(), "files": {}}
            with tarfile.open(fileobj=process.stdin, mode="w|gz") as archive:
                for name in sorted(INCLUDED):
                    base = store.root / name
                    if not base.exists(): raise DeskError("A required backup folder or file is missing: " + name)
                    for path in ([base] if base.is_file() else sorted(base.rglob("*"))):
                        if "__pycache__" in path.parts or path.name.endswith(".lock") or path.name.startswith(".write-"): continue
                        if path.is_symlink(): raise DeskError("Backup contains a symbolic link; review it locally")
                        if not path.is_file(): continue
                        relative = path.relative_to(store.root).as_posix()
                        content = path.read_bytes()
                        manifest["files"][relative] = hashlib.sha256(content).hexdigest()
                        entry = tarfile.TarInfo(relative)
                        entry.size, entry.mode = len(content), 0o600
                        archive.addfile(entry, io.BytesIO(content))
                content = json.dumps(manifest).encode()
                entry = tarfile.TarInfo("snapshot-manifest.json")
                entry.size, entry.mode = len(content), 0o600
                archive.addfile(entry, io.BytesIO(content))
            process.stdin.close()
            error = process.stderr.read(10000)
            if process.wait(timeout=120) != 0: raise DeskError("Encryption failed; no backup published")
            encrypted.flush()
            os.fsync(encrypted.fileno())
        # Exclusive publish; do not overwrite an earlier backup.
        os.link(temporary, output)
        return {"encrypted": True, "archive": str(output), "files": len(manifest["files"]),
                "restore_tested": False, "company_id": manifest["company_id"]}
    finally:
        if process and process.poll() is None:
            process.kill()
            process.wait()
        if process:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream and not stream.closed:
                    try: stream.close()
                    except BrokenPipeError: pass
        Path(temporary).unlink(missing_ok=True)


def restore(root, archive_path, identity):
    root = Path(root).expanduser().resolve()
    if root.exists(): raise DeskError("Restore into a new folder; never overwrite a running company")
    root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".puestario-restore-", dir=root.parent))
    process = None
    try:
        process = subprocess.Popen(["age", "-d", "-i", str(identity), str(archive_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        observed, total, manifest = {}, 0, None
        with tarfile.open(fileobj=process.stdout, mode="r|gz") as archive:
            for entry in archive:
                relative = safe_name(entry.name)
                if not entry.isfile() or entry.name in observed or entry.size < 0:
                    raise DeskError("Backup contains a link, duplicate or unsupported entry")
                total += entry.size
                if total > MAX_RESTORE_BYTES: raise DeskError("Backup exceeds the restore size limit")
                source = archive.extractfile(entry)
                content = source.read()
                if len(content) != entry.size: raise DeskError("Backup is incomplete")
                observed[entry.name] = hashlib.sha256(content).hexdigest()
                if entry.name == "snapshot-manifest.json": manifest = json.loads(content)
                else:
                    destination = temporary / str(relative)
                    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    destination.write_bytes(content)
                    destination.chmod(0o600)
        process.stdout.close()
        process.stderr.read(10000)
        if process.wait(timeout=120) != 0: raise DeskError("Decryption failed")
        observed.pop("snapshot-manifest.json", None)
        if not manifest or observed != manifest.get("files"):
            raise DeskError("Backup file hashes do not match")
        state = json.loads((temporary / "control.json").read_text())
        if manifest["company_id"] != state["company"]["company_id"]:
            raise DeskError("Backup company does not match")
        state.update(paused=True, ready=False, mode="SETUP", setup=None, checks={}, sessions={}, gateway_pending=True,
                     access_epoch=state.get("access_epoch", 0) + 1, boot=None)
        state["install"].update(release=str(root / "release"), gateway_token=secrets.token_urlsafe(36))
        for job in state["jobs"].values():
            job["enabled"] = False
            for run in job["runs"]:
                if run["status"] in {"sending", "preparing"}: run["status"] = "unverified"
        for notice in state["outbox"].values():
            if notice["status"] in {"pending", "sending"}: notice["status"] = "cancelled-on-restore"
        atomic_json(temporary / "control.json", state)
        config = managed_config(state, root, root / "release")
        # Preserve the logger location in pre-cleanup encrypted snapshots. This
        # restores archived code, not a migration or execution of that code.
        logger = Path("managed/action_log.py")
        if not (temporary / "release" / logger).is_file():
            logger = Path("core/scripts/action_log.py")
            if not (temporary / "release" / logger).is_file():
                raise DeskError("Backup is missing its outbound logger; use a complete reviewed snapshot")
        config["plugins"]["entries"]["action-log"]["config"]["script"] = str(root / "release" / logger)
        atomic_json(temporary / "gateway/openclaw.json", config)
        for name, content in workspace_files(state).items():
            path = temporary / "workspace" / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_text(content)
            path.chmod(0o400)
        # The old machine's WhatsApp and model identities must be reviewed before startup.
        os.rename(temporary, root)
        for folder in ("security", "secrets", "evidence", "workspace", "gateway", "backups"):
            (root / folder).mkdir(mode=0o700, exist_ok=True)
        return {"restored": True, "root": str(root), "paused": True, "jobs_enabled": 0,
                "next": "Stop the old machine; verify this company's account, phone, models, app access and job times before resuming"}
    finally:
        if process and process.poll() is None:
            process.kill()
            process.wait()
        if process:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream and not stream.closed: stream.close()
        if temporary.exists(): shutil.rmtree(temporary)


def retention_candidates(files, company_id, keep_days, now=None):
    """Only this application's labelled encrypted backups, never arbitrary folder contents."""
    if type(keep_days) is not int or keep_days < 7: raise DeskError("Keep at least seven days of backups")
    now = time.time() if now is None else now
    from datetime import datetime
    eligible = []
    for row in files:
        props = row.get("appProperties", {})
        if props.get("puestarioCompany") != company_id or props.get("puestarioBackup") != "age-v1": continue
        if not row.get("name", "").startswith(f"puestario-{company_id}-") or not row["name"].endswith(".age"): continue
        created = datetime.fromisoformat(row["createdTime"].replace("Z", "+00:00")).timestamp()
        eligible.append((created, row["id"]))
    eligible.sort(reverse=True)
    # Always retain the newest verified backup, even if every file is old.
    return [file_id for created, file_id in eligible[1:] if created < now - keep_days * 86400]
