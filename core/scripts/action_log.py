#!/usr/bin/env python3
"""Append-only, hash-chained action log for everything the desk does to the world.

    action_log.py verify  [--path PATH]                      walk the chain; exit 1 on any edit
    action_log.py list    [--path PATH]                      print every action with its joined outcome
    action_log.py record  --action A --target T --payload-class P --consent C [--payload-stdin]
                                                             append the action line; print the receipt id
    action_log.py outcome --receipt ID --status S           append the outcome line for a receipt

``record`` and ``outcome`` exist so a runtime hook written in another language
(the OpenClaw plugin under runtimes/openclaw/) can call this one implementation
instead of re-implementing the chain. Exit 0 and the receipt id on stdout mean
the line is on disk; any other exit means it is not, and the caller must not
send.

Modelled on gstack's lib/egress-receipt.ts. The log answers one question after
the fact: what did the desk attempt, when, against what, and what came back.

Semantics:

- Action-before-side-effect. The action line is appended BEFORE the send, the
  write, the call. An adapter that cannot write the line refuses to act and
  returns ``unavailable`` with code ``action_log_unwritable``. Nothing leaves
  the machine unrecorded.
- Outcome-after. The outcome line is best effort bookkeeping: the action line
  is the invariant, the outcome joins to it by receipt id.
- Content-free. Never the message text, never a credential. A sha256 of the
  exact payload bytes plus a byte count, so a line can prove what was sent
  without containing it.
- Tamper-evident. Every line carries ``prev`` = sha256 of the previous raw
  line ("" for line 1). ``verify`` recomputes the whole chain and reports the
  first line that no longer matches. An edit, a deletion or an insertion
  anywhere breaks every line after it.

The log is forensic. It records attempts so mistakes are auditable. It is not
an access control and does not stop anything on its own.

Location, in order: ``$ACTION_LOG`` when set; else
``$OPENCLAW_STATE_DIR/security/action-log.jsonl``; else
``$HERMES_HOME/security/action-log.jsonl``. There is no home-folder default: an
install that has not set one of those variables cannot write the log, and
every sender that honours the log refuses to send until it can. Created 0600
inside a 0700 directory. Standard library only.
"""
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ACTION_LOG_FAILED = "ACTION_LOG_FAILED"
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
MAX_FIELD_BYTES = 512
TAIL_READ_BYTES = 4096
LOCK_BUDGET_SECONDS = 2.5
STALE_LOCK_SECONDS = 10


class ActionLogError(Exception):
    code = ACTION_LOG_FAILED


PATH_ENV = ("ACTION_LOG", "OPENCLAW_STATE_DIR", "HERMES_HOME")


def default_path() -> Path:
    """Resolve the log path from the environment. Raises when nothing is set."""
    configured = os.environ.get("ACTION_LOG")
    if configured:
        return Path(configured)
    for var in ("OPENCLAW_STATE_DIR", "HERMES_HOME"):
        home = os.environ.get(var)
        if home:
            return Path(home) / "security" / "action-log.jsonl"
    raise ActionLogError("no action log path: set ACTION_LOG, OPENCLAW_STATE_DIR or HERMES_HOME")


def sha256_hex(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _require_field(value, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ActionLogError(f"action log requires a non-empty {name}")
    if "\n" in value or "\r" in value:
        raise ActionLogError(f"action log {name} must not contain a newline")
    if len(value.encode("utf-8")) > MAX_FIELD_BYTES:
        raise ActionLogError(f"action log {name} exceeds {MAX_FIELD_BYTES} bytes")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _last_raw_line(path: Path):
    """Last newline-terminated line via a tail read; never loads the whole file."""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            if size == 0:
                return None
            length = min(size, TAIL_READ_BYTES)
            handle.seek(size - length)
            tail = handle.read(length).decode("utf-8", errors="replace")
    except FileNotFoundError:
        return None
    lines = [line for line in tail.split("\n") if line]
    return lines[-1] if lines else None


class _Lock:
    """mkdir spin lock: portable, and a crashed writer's stale lock is reclaimed."""

    def __init__(self, path: Path, budget: float = None):
        self.lock = Path(str(path) + ".lock")
        self.budget = LOCK_BUDGET_SECONDS if budget is None else budget

    def __enter__(self):
        deadline = time.monotonic() + max(0.0, self.budget)
        while True:
            try:
                self.lock.mkdir()
                return self
            except FileExistsError:
                if time.monotonic() > deadline:
                    try:
                        if time.time() - self.lock.stat().st_mtime > STALE_LOCK_SECONDS:
                            self.lock.rmdir()
                            continue
                    except OSError:
                        continue
                    raise ActionLogError(f"action log is locked: {self.lock}")
                time.sleep(0.01)

    def __exit__(self, *exc):
        try:
            self.lock.rmdir()
        except OSError:
            pass
        return False


def _append_chained(record: dict, path=None) -> str:
    path = Path(path) if path else default_path()  # raises ActionLogError when unset
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with _Lock(path):
            previous = _last_raw_line(path)
            line = json.dumps({**record, "prev": "" if previous is None else sha256_hex(previous)},
                              separators=(",", ":"), ensure_ascii=True)
            if "\n" in line:
                raise ActionLogError("action log record serialized to more than one line")
            existed = path.exists()
            fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, (line + "\n").encode("utf-8"))
            finally:
                os.close(fd)
            if not existed:
                os.chmod(path, 0o600)
            return sha256_hex(line)
    except ActionLogError:
        raise
    except OSError as exc:
        raise ActionLogError(f"action log could not be written to {path}: {exc.__class__.__name__}") from exc


def write_action(*, action: str, target: str, payload_class: str, consent: str,
                 payload: bytes = None, path=None) -> str:
    """Append one content-free action line BEFORE the side effect.

    Returns the receipt id: sha256 of the written line. Raises ActionLogError
    when the line cannot be written; callers about to act must then refuse.
    """
    record = {
        "ts": _now(),
        "type": "action",
        "action": _require_field(action, "action"),
        "target": _require_field(target, "target"),
        "payload_class": _require_field(payload_class, "payload_class"),
        "bytes": 0 if payload is None else len(payload),
        "sha256": None if payload is None else sha256_hex(payload),
        "consent": _require_field(consent, "consent"),
    }
    if payload is not None and not isinstance(payload, (bytes, bytearray)):
        raise ActionLogError("action log payload must be bytes")
    return _append_chained(record, path)


def write_outcome(*, receipt: str, status, path=None) -> str:
    """Append the outcome for an earlier action. Chained like every other line."""
    receipt = _require_field(receipt, "receipt")
    if not SHA256_HEX.match(receipt):
        raise ActionLogError("action log receipt must be 64 lowercase hex chars")
    return _append_chained({"ts": _now(), "type": "outcome", "receipt": receipt,
                            "status": _require_field(str(status), "status")}, path)


def read_log(path=None):
    """Raw parsed lines: [(line_no, raw, record_or_None)]. Missing or unconfigured log: []."""
    try:
        path = Path(path) if path else default_path()
    except ActionLogError:
        return []
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    lines = []
    for index, raw in enumerate(line for line in content.split("\n") if line):
        record = None
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                record = parsed
        except ValueError:
            pass
        lines.append((index + 1, raw, record))
    return lines


def verify(path=None) -> dict:
    """Recompute the chain. broken_line is the first line whose prev no longer matches."""
    lines = read_log(path)
    previous_raw = None
    for line_no, raw, record in lines:
        if record is None or not isinstance(record.get("prev"), str):
            return {"ok": False, "count": len(lines), "broken_line": line_no,
                    "reason": "unparseable or missing prev"}
        expected = "" if previous_raw is None else sha256_hex(previous_raw)
        if record["prev"] != expected:
            return {"ok": False, "count": len(lines), "broken_line": line_no,
                    "reason": "prev hash does not match previous line"}
        previous_raw = raw
    return {"ok": True, "count": len(lines), "broken_line": None, "reason": None}


def list_actions(path=None):
    """Action records with their joined outcome status (None when none recorded)."""
    actions, by_id = [], {}
    for _, raw, record in read_log(path):
        if not record:
            continue
        if record.get("type") == "action":
            entry = {**record, "id": sha256_hex(raw), "status": None}
            actions.append(entry)
            by_id[entry["id"]] = entry
        elif record.get("type") == "outcome" and record.get("receipt") in by_id:
            by_id[record["receipt"]]["status"] = str(record.get("status"))
    return actions


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Append-only, hash-chained action log.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("verify", "list"):
        sub.add_parser(name).add_argument("--path", default=None)
    rec = sub.add_parser("record")
    rec.add_argument("--action", required=True)
    rec.add_argument("--target", required=True)
    rec.add_argument("--payload-class", required=True)
    rec.add_argument("--consent", required=True)
    rec.add_argument("--payload-stdin", action="store_true", help="hash the exact bytes on stdin")
    rec.add_argument("--path", default=None)
    out = sub.add_parser("outcome")
    out.add_argument("--receipt", required=True)
    out.add_argument("--status", required=True)
    out.add_argument("--path", default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            result = verify(args.path)
            print(json.dumps(result))
            return 0 if result["ok"] else 1
        if args.command == "list":
            for entry in list_actions(args.path):
                print(json.dumps(entry))
            return 0
        if args.command == "record":
            payload = sys.stdin.buffer.read() if args.payload_stdin else None
            print(write_action(action=args.action, target=args.target, payload_class=args.payload_class,
                               consent=args.consent, payload=payload, path=args.path))
            return 0
        print(write_outcome(receipt=args.receipt, status=args.status, path=args.path))
        return 0
    except ActionLogError as exc:
        print(f"action_log: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
