"""Local operator CLI and private stdin bridge. Never expose this command as an agent shell."""
import argparse
import getpass
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from . import control, install, runtime
from .store import DeskError, Store, atomic_json


def envelope():
    raw = sys.stdin.read(1_000_001)
    if len(raw) > 1_000_000: raise DeskError("Request is too large")
    value = json.loads(raw)
    if not isinstance(value, dict): raise DeskError("Provide one JSON object")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--company", required=True, type=Path)
    init.add_argument("--source", default=Path(__file__).resolve().parents[1], type=Path)
    init.add_argument("--revision", required=True)
    init.add_argument("--port", type=int, default=18791)
    init.add_argument("--staging", action="store_true", help="Offline fixture only; can never pass acceptance")
    for name in ("request", "session-gate", "startup", "tick", "apply", "acknowledge", "doctor", "status", "service-file"):
        sub.add_parser(name)
    accept = sub.add_parser("accept")
    accept.add_argument("check", choices=sorted(control.CHECKS))
    accept.add_argument("--evidence", type=Path, required=True)
    accept.add_argument("--operator", required=True)
    token = sub.add_parser("connect-token")
    token.add_argument("name")
    google = sub.add_parser("connect-google")
    google.add_argument("name")
    google.add_argument("--client", type=Path, required=True)
    google.add_argument("--scope", action="append", required=True)
    oc = sub.add_parser("openclaw")
    oc.add_argument("arguments", nargs=argparse.REMAINDER)
    backup = sub.add_parser("backup")
    backup.add_argument("--recipient", required=True)
    backup.add_argument("--output", required=True, type=Path)
    restore = sub.add_parser("restore")
    restore.add_argument("--identity", required=True, type=Path)
    restore.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    store = Store(args.root)
    try:
        if args.command == "init":
            result = install.initialize(args.root, args.source, json.loads(args.company.read_text()), args.revision, args.port, args.staging)
        elif args.command == "request":
            data = envelope()
            if data.get("direct_command"):
                control.require_founder(store.read(), data["actor"], __import__("time").time())
            else:
                control.session_gate(store, data["actor"], data.get("session_id"))
            result = control.dispatch(store, data["actor"], data["operation"], data.get("args"),
                                      data.get("request_id"), data.get("expected_revision"))
            if store.read()["gateway_pending"]:
                try:
                    applied = runtime.apply(store)
                    result = {**result, "settings_applied": applied["applied"], "note": "Saved and validated; live gateway acknowledgement is checked separately"}
                except DeskError:
                    result = {**result, "settings_applied": False, "note": "Saved, but gateway settings need a local operator check"}
        elif args.command == "session-gate":
            data = envelope()
            result = control.session_gate(store, data["actor"], data.get("session_id"), data.get("has_history", False))
        elif args.command == "startup":
            runtime.startup(store, envelope()["boot"])
            result = {"started": True}
        elif args.command == "tick": result = runtime.tick(store)
        elif args.command == "apply": result = runtime.apply(store)
        elif args.command == "acknowledge": result = runtime.acknowledge(store, envelope()["config"])
        elif args.command == "doctor": result = install.doctor(store)
        elif args.command == "status": result = control.public_status(store.read(), True)
        elif args.command == "service-file": result = install.service_file(store)
        elif args.command == "accept": result = install.accept(store, args.check, args.evidence, args.operator)
        elif args.command == "connect-token":
            store.read()
            control.slug(args.name)
            if not sys.stdin.isatty(): raise DeskError("Enter credentials in the local terminal, never a model tool or chat")
            token = getpass.getpass("Paste this company's restricted app token (hidden): ")
            if len(token) < 8: raise DeskError("Credential was not saved")
            atomic_json(store.root / "secrets" / (args.name + ".json"), {"token": token})
            result = {"saved": True, "connected": False, "next": "Run connection.check against the configured resource"}
        elif args.command == "connect-google":
            store.read()
            from .oauth import connect
            result = connect(store, args.name, args.client, args.scope)
        elif args.command == "openclaw":
            store.read()
            return subprocess.run(["openclaw", *args.arguments], env=runtime.environment(store.root)).returncode
        elif args.command == "backup":
            from .backup import backup
            result = backup(store, args.recipient, args.output)
        elif args.command == "restore":
            from .backup import restore
            result = restore(store.root, args.archive, args.identity)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
        return 0 if not (args.command == "doctor" and not result["passed"]) else 1
    except (DeskError, OSError, ValueError, TypeError, KeyError, tarfile.TarError, subprocess.SubprocessError) as exc:
        message = str(exc) if isinstance(exc, DeskError) else "Local setup operation failed; check the input and private machine log"
        print(json.dumps({"ok": False, "error": message}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
