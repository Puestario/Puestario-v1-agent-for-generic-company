#!/usr/bin/env python3
"""Wrap one agent trial and write the record evals/score.py expects.

    python3 evals/run.py --case CASE_ID --requested-model MODEL \\
        [--actual-model MODEL] [--fallback-reason TEXT] \\
        [--input FILE]... [--trial-id ID] [--reviewer NAME] \\
        [--tool-calls N] [--cost-usd X] [--records FILE] [--log-dir DIR] \\
        -- <command that runs the trial>

Modelled on gstack's bin/gstack-evidence, with one change: the fingerprint is
the sha256 of the input files you name, not a git tree. A trial is bound to the
exact prompt, config and fixture bytes it ran against, wherever they live.

What the wrapper does, in order:

1. Refuses to start when the case id is not in evals/cases.json or an input
   file is missing. Exit 2, nothing recorded.
2. Hashes every input file BEFORE the command runs. ``config_revision`` is the
   sha256 over the sorted ``path:sha256`` lines.
3. Runs the command, streams its output through unchanged and tees it to a
   0600 log file under ``--log-dir`` (2 MB cap with a truncation marker).
4. Hashes the inputs again. If any byte changed during the run the record says
   ``input_fingerprint_stable: false``; the trial then certifies nothing.
5. Writes the record. ``requested_model`` is what you asked for.
   ``actual_model`` is ``--actual-model`` when given, else the last
   ``actual_model=<id>`` line the runtime printed, else null with a warning.
   A trial whose actual model differs from the requested one is a fallback:
   ``fallback_reason`` comes from ``--fallback-reason`` and
   ``fallback_disclosed`` is whether the output mentions the fallback (the
   reviewer confirms it). ``result`` is the last JSON object on stdout that
   has a ``status`` field, so an adapter's tool result is captured as is.
6. Leaves ``review_passed`` false and ``reviewer`` empty. A human reads the
   log against the case rubric, sets both, and only then does the record
   score. The wrapper never grades a trial.

TRANSPARENCY: the command's exit code is always the wrapper's exit code. A
bookkeeping failure is a warning on stderr, never a changed result.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.json"
DEFAULT_RECORDS = HERE / "records" / "trials.json"
DEFAULT_LOG_DIR = HERE / "logs"
LOG_MAX_BYTES = 2 * 1024 * 1024
MODEL_LINE = re.compile(r"^\s*actual_model\s*=\s*(\S+)\s*$", re.M)
DISCLOSURE = re.compile(r"\b(fallback|degraded|fell back)\b", re.I)


def warn(message: str) -> None:
    print(f"evals/run: warning: {message}", file=sys.stderr)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(paths) -> dict:
    """{'files': {path: sha256}, 'config_revision': sha256 over sorted path:sha lines}."""
    files = {str(path): sha256_file(path) for path in paths}
    lines = "\n".join(f"{name}:{digest}" for name, digest in sorted(files.items()))
    return {"files": files, "config_revision": hashlib.sha256(lines.encode()).hexdigest()}


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Record one agent trial.", add_help=True)
    parser.add_argument("--case", required=True, help="case id from evals/cases.json")
    parser.add_argument("--requested-model", required=True)
    parser.add_argument("--actual-model")
    parser.add_argument("--fallback-reason")
    parser.add_argument("--input", action="append", default=[], help="input file to fingerprint; repeatable")
    parser.add_argument("--trial-id", default="1")
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--tool-calls", type=int, default=0)
    parser.add_argument("--cost-usd", type=float, default=0.0)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--log-max-bytes", type=int, default=LOG_MAX_BYTES, help=argparse.SUPPRESS)
    if "--" not in argv:
        parser.error("give the trial command after --")
    split = argv.index("--")
    args = parser.parse_args(argv[:split])
    args.command = argv[split + 1:]
    if not args.command:
        parser.error("give the trial command after --")
    if args.tool_calls < 0 or args.cost_usd < 0:
        parser.error("--tool-calls and --cost-usd must not be negative")
    return args


def open_log(log_dir: Path, case: str):
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = f"{stamp}-{case}-{os.getpid()}"
    for suffix in ("", "-1", "-2"):
        path = log_dir / f"{base}{suffix}.log"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            return fd, path
        except FileExistsError:
            continue
    raise OSError("could not create a log file")


def run_command(command, log_fd, log_max_bytes):
    """Stream the child's combined output to stdout and the log. Returns (exit, output)."""
    try:
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as exc:
        warn(f"spawn failed: {exc.__class__.__name__}")
        return 127, b""
    captured = bytearray()
    logged = 0
    truncated = False
    for chunk in iter(lambda: child.stdout.read(4096), b""):
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
        captured.extend(chunk)
        if log_fd is None or truncated:
            continue
        try:
            room = log_max_bytes - logged
            if len(chunk) > room:
                if room > 0:
                    os.write(log_fd, chunk[:room])
                os.write(log_fd, b"\n\n[evals/run: log truncated; output continued on console]\n")
                truncated = True
            else:
                os.write(log_fd, chunk)
                logged += len(chunk)
        except OSError:
            truncated = True
    return child.wait(), bytes(captured)


def last_result(output: bytes):
    """The last JSON object on the output that carries a status field, else None."""
    for line in reversed(output.decode("utf-8", errors="replace").splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("status"), str):
            return parsed
    return None


def append_record(records_path: Path, record: dict) -> None:
    records_path.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if records_path.exists():
        existing = json.loads(records_path.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            raise ValueError("records file is not a JSON array")
    existing.append(record)
    tmp = records_path.with_suffix(records_path.suffix + ".tmp")
    tmp.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, records_path)


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        case_ids = {case["id"] for case in json.loads(args.cases.read_text(encoding="utf-8"))}
    except (OSError, ValueError, KeyError, TypeError):
        print(f"evals/run: cannot read cases from {args.cases}", file=sys.stderr)
        return 2
    if args.case not in case_ids:
        print(f"evals/run: unknown case id {args.case!r}; see {args.cases}", file=sys.stderr)
        return 2
    inputs = [Path(p) for p in args.input]
    missing = [str(p) for p in inputs if not p.is_file()]
    if missing:
        print(f"evals/run: input file(s) missing: {', '.join(missing)}", file=sys.stderr)
        return 2

    before = fingerprint(inputs)
    log_fd, log_path = None, None
    try:
        log_fd, log_path = open_log(args.log_dir, args.case)
    except OSError as exc:
        warn(f"log setup failed ({exc.__class__.__name__}); running unlogged")

    started = time.monotonic()
    started_at = datetime.now(timezone.utc)
    exit_code, output = run_command(args.command, log_fd, args.log_max_bytes)
    latency_ms = int((time.monotonic() - started) * 1000)
    if log_fd is not None:
        os.close(log_fd)

    try:
        after = fingerprint(inputs)
    except OSError:
        after = {"config_revision": None, "files": {}}
    stable = after["config_revision"] == before["config_revision"]
    if not stable:
        warn("input files changed during the run; this trial certifies nothing")

    text = output.decode("utf-8", errors="replace")
    actual = args.actual_model
    if actual is None:
        found = MODEL_LINE.findall(text)
        actual = found[-1] if found else None
    if actual is None:
        warn("actual model unknown: pass --actual-model or have the runtime print actual_model=<id>")
    fallback = actual is not None and actual != args.requested_model
    if fallback and not args.fallback_reason:
        warn("fallback happened but no --fallback-reason was given")

    result = last_result(output)
    if result is None:
        result = {"status": "succeeded" if exit_code == 0 else "failed", "evidence": []}
        warn("no tool result JSON found on stdout; status inferred from the exit code")

    record = {
        "case_id": args.case,
        "run_id": f"{args.case}-{started_at.strftime('%Y%m%dT%H%M%S%fZ')}-{os.getpid()}",
        "trial_id": args.trial_id,
        "requested_model": args.requested_model,
        "actual_model": actual,
        "config_revision": before["config_revision"],
        "input_files": before["files"],
        "input_fingerprint_stable": stable,
        "provenance": "runtime",
        "fallback_reason": args.fallback_reason if fallback else None,
        "fallback_disclosed": bool(fallback and DISCLOSURE.search(text)),
        "tool_calls": args.tool_calls,
        "latency_ms": latency_ms,
        "cost_usd": args.cost_usd,
        "command": args.command,
        "exit_code": exit_code,
        "started_at": started_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "final_status": result["status"],
        "result": result,
        "review_passed": False,
        "reviewer": args.reviewer,
        "review_evidence": str(log_path) if log_path else "",
    }
    try:
        append_record(args.records, record)
        print(f"evals/run: recorded case={args.case} exit={exit_code} status={result['status']} "
              f"log={log_path or '-'} records={args.records}", file=sys.stderr)
    except (OSError, ValueError) as exc:
        warn(f"record not written ({exc.__class__.__name__}); the command result stands")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
