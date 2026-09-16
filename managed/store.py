"""Private, locked, atomic state. The host service owns this directory, not the model."""
import contextlib
import copy
import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path


class DeskError(Exception):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise DeskError("Refusing a linked state file")
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        folder = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Store:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.path = self.root / "control.json"

    @contextlib.contextmanager
    def locked(self):
        if not self.path.is_file() or self.path.is_symlink():
            raise DeskError("This company has not been initialized")
        fd = os.open(self.root / ".control.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            state = json.loads(self.path.read_text())
            original = copy.deepcopy(state)
            yield state
            if state != original:
                atomic_json(self.path, state)
        finally:
            os.close(fd)

    def read(self):
        with self.locked() as state:
            return copy.deepcopy(state)

    def initialize(self, state):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        # Never reset an installed company or silently replace its owners.
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(state, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            self.path.unlink(missing_ok=True)
            raise


def record(state, actor, action, details, now):
    records = state.setdefault("history", [])
    entry = {"at": now, "actor": actor, "action": action, "details": details,
             "previous": digest(records[-1]) if records else ""}
    records.append(entry)
    state["revision"] += 1
    return state["revision"]
