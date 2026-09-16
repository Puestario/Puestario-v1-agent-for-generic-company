#!/usr/bin/env python3
"""Validated appends to client/memory/learnings.jsonl and decisions.jsonl.

    memory_log.py learn     '{"type":"pitfall","key":"...","insight":"...","confidence":8,"source":"observed"}'
    memory_log.py decide    '{"decision":"...","rationale":"...","scope":"rules","source":"owner"}'
    memory_log.py supersede <decision-id> ['{...replacement decide payload...}']
    memory_log.py active    print the decisions still in force, one JSON line each
    memory_log.py current   print the current learnings (latest per type+key), one JSON line each
    memory_log.py brief     print both as a short Markdown block for the start of a session
    memory_log.py verify    validate both files; exit 1 on any bad line

Fields follow gstack's learnings and decision stores (bin/gstack-learnings-log,
lib/gstack-decision.ts). Both files are append-only. A duplicate learning
(same type and key) is resolved at read time: the latest line wins. A decision
is retired by a ``supersede`` event that names its id; the log is never edited.

Trust is recorded, not assumed: ``trusted`` is true only when an owner stated
the learning themselves (``source: user-stated``). Everything the agent
observed or inferred is untrusted memory and is read as such.

``source`` is the trust gate. Text from an untrusted source (learnings marked
observed, inferred or cross-model; decisions marked agent) is scanned with
core/scripts/untrusted.py and rejected if it reads like an instruction, so
nothing that came in through content can park itself in memory and be re-read
later as if it were an owner's voice. Text from a trusted source (learnings
marked user-stated; decisions marked owner or installer) is not scanned: an
owner's order is supposed to read like an order, and rule 06 requires the
agent to record exactly what the owner asked for. Marking a line as owner-
sourced when it did not come from an owner's verified number is a rule 05
violation, not a memory problem.

Location: ``$MEMORY_DIR`` when set, else ``client/memory/`` next to ``core/``.
"""
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import untrusted  # noqa: E402

LEARNING_TYPES = ("pattern", "pitfall", "preference", "architecture", "tool", "operational", "investigation")
LEARNING_SOURCES = ("observed", "user-stated", "inferred", "cross-model")
TRUSTED_LEARNING_SOURCES = ("user-stated",)
DECISION_KINDS = ("decide", "supersede")
DECISION_SCOPES = ("rules", "tools", "allowlist", "channels", "money", "job", "other")
DECISION_SOURCES = ("owner", "installer", "agent")
TRUSTED_DECISION_SOURCES = ("owner", "installer")
KEY_RE = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MAX_TEXT_CHARS = 2000


class MemoryLogError(ValueError):
    pass


def memory_dir() -> Path:
    configured = os.environ.get("MEMORY_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "client" / "memory"


def learnings_path() -> Path:
    return memory_dir() / "learnings.jsonl"


def decisions_path() -> Path:
    return memory_dir() / "decisions.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _text(record, field, required, scan=True):
    value = record.get(field)
    if value is None:
        if required:
            raise MemoryLogError(f"{field} is required")
        return None
    if not isinstance(value, str) or not value.strip():
        raise MemoryLogError(f"{field} must be a non-empty string")
    if len(value) > MAX_TEXT_CHARS:
        raise MemoryLogError(f"{field} exceeds {MAX_TEXT_CHARS} characters")
    if "\n" in value or "\r" in value:
        raise MemoryLogError(f"{field} must be one line")
    if scan and untrusted.line_looks_like_instruction(value):
        raise MemoryLogError(f"{field} reads like an instruction and its source is not trusted; rejected")
    return value


def _confidence(record, required):
    value = record.get("confidence")
    if value is None:
        if required:
            raise MemoryLogError("confidence is required")
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10:
        raise MemoryLogError("confidence must be an integer from 1 to 10")
    return value


def validate_learning(record: dict) -> dict:
    if not isinstance(record, dict):
        raise MemoryLogError("a learning is a JSON object")
    if record.get("type") not in LEARNING_TYPES:
        raise MemoryLogError(f"type must be one of: {', '.join(LEARNING_TYPES)}")
    key = record.get("key")
    if not isinstance(key, str) or not KEY_RE.match(key):
        raise MemoryLogError("key must be letters, digits, hyphens or underscores")
    if record.get("source") not in LEARNING_SOURCES:
        raise MemoryLogError(f"source must be one of: {', '.join(LEARNING_SOURCES)}")
    trusted = record["source"] in TRUSTED_LEARNING_SOURCES
    out = {
        "ts": record.get("ts") or _now(),
        "type": record["type"],
        "key": key,
        "insight": _text(record, "insight", required=True, scan=not trusted),
        "confidence": _confidence(record, required=True),
        "source": record["source"],
        "trusted": trusted,
    }
    if "trusted" in record and record["trusted"] != out["trusted"]:
        raise MemoryLogError("trusted is derived from source; it cannot be set by hand")
    return out


def validate_decision(record: dict) -> dict:
    if not isinstance(record, dict):
        raise MemoryLogError("a decision is a JSON object")
    kind = record.get("kind", "decide")
    if kind not in DECISION_KINDS:
        raise MemoryLogError(f"kind must be one of: {', '.join(DECISION_KINDS)}")
    if record.get("scope") not in DECISION_SCOPES:
        raise MemoryLogError(f"scope must be one of: {', '.join(DECISION_SCOPES)}")
    if record.get("source") not in DECISION_SOURCES:
        raise MemoryLogError(f"source must be one of: {', '.join(DECISION_SOURCES)}")
    scan = record["source"] not in TRUSTED_DECISION_SOURCES
    ident = record.get("id") or str(uuid.uuid4())
    if not isinstance(ident, str) or not UUID_RE.match(ident):
        raise MemoryLogError("id must be a lowercase UUID")
    out = {"id": ident, "kind": kind, "date": record.get("date") or _now(),
           "scope": record["scope"], "source": record["source"]}
    if kind == "decide":
        out["decision"] = _text(record, "decision", required=True, scan=scan)
        out["rationale"] = _text(record, "rationale", required=True, scan=scan)
        alternatives = _text(record, "alternatives_considered", required=False, scan=scan)
        if alternatives:
            out["alternatives_considered"] = alternatives
        confidence = _confidence(record, required=False)
        if confidence is not None:
            out["confidence"] = confidence
    supersedes = record.get("supersedes")
    if kind == "supersede" and not supersedes:
        raise MemoryLogError("a supersede event names the decision id it retires")
    if supersedes is not None:
        if not isinstance(supersedes, str) or not UUID_RE.match(supersedes):
            raise MemoryLogError("supersedes must be a lowercase UUID")
        out["supersedes"] = supersedes
    return out


def _append(path: Path, record: dict) -> None:
    line = json.dumps(record, ensure_ascii=False)
    if "\n" in line:
        raise MemoryLogError("record serialized to more than one line")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read_lines(path: Path, validator):
    """Every line validated; a bad line raises MemoryLogError naming its number."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    records = []
    for number, raw in enumerate(text.split("\n"), 1):
        if not raw.strip():
            continue
        try:
            records.append(validator(json.loads(raw)))
        except (ValueError, MemoryLogError) as exc:
            raise MemoryLogError(f"{path.name} line {number}: {exc}") from exc
    return records


def learn(record: dict) -> dict:
    validated = validate_learning(record)
    _append(learnings_path(), validated)
    return validated


def decide(record: dict) -> dict:
    validated = validate_decision({**record, "kind": "decide"})
    _append(decisions_path(), validated)
    return validated


def supersede(target_id: str, replacement: dict = None, source: str = "agent") -> list:
    """Retire a decision. The replacement, if any, is written FIRST so it is never lost."""
    if not isinstance(target_id, str) or not UUID_RE.match(target_id):
        raise MemoryLogError("supersede needs the id of the decision it retires")
    known = {d["id"] for d in read_lines(decisions_path(), validate_decision) if d["kind"] == "decide"}
    if target_id not in known:
        raise MemoryLogError("supersede target is not a recorded decision")
    written = []
    if replacement is not None:
        validated = validate_decision({**replacement, "kind": "decide", "supersedes": target_id})
        _append(decisions_path(), validated)
        written.append(validated)
    event = validate_decision({"kind": "supersede", "supersedes": target_id, "scope": "other", "source": source})
    _append(decisions_path(), event)
    written.append(event)
    return written


def current_learnings() -> list:
    """Latest line per (type, key) wins; earlier lines stay in the file as history."""
    latest = {}
    for record in read_lines(learnings_path(), validate_learning):
        latest[(record["type"], record["key"])] = record
    return list(latest.values())


def active_decisions() -> list:
    events = read_lines(decisions_path(), validate_decision)
    retired = {e["supersedes"] for e in events if e["kind"] == "supersede"}
    return [e for e in events if e["kind"] == "decide" and e["id"] not in retired]


def brief() -> str:
    """Markdown block of what is in force, read at the start of every session (AGENTS.md section 0)."""
    decisions = active_decisions()
    learnings = sorted(current_learnings(), key=lambda r: (r["type"], r["key"]))
    lines = ["# Memory brief", "",
             "Generated by core/scripts/memory_log.py brief at session start. Do not edit; append",
             "through the script. Decisions here are in force until superseded. Learnings marked",
             "trusted came from an owner; the rest are the agent's own observations.", "",
             f"## Decisions in force ({len(decisions)})", ""]
    for d in decisions:
        lines.append(f"- [{d['date'][:10]}] [{d['scope']}] {d['decision']} (source: {d['source']}; why: {d['rationale']})")
    if not decisions:
        lines.append("- (none recorded)")
    lines += ["", f"## Current learnings ({len(learnings)})", ""]
    for r in learnings:
        trust = "trusted" if r["trusted"] else "untrusted"
        lines.append(f"- [{r['type']}/{r['key']}] ({trust}, confidence {r['confidence']}/10) {r['insight']}")
    if not learnings:
        lines.append("- (none recorded)")
    return "\n".join(lines) + "\n"


def verify() -> dict:
    problems = []
    for path, validator in ((learnings_path(), validate_learning), (decisions_path(), validate_decision)):
        try:
            read_lines(path, validator)
        except MemoryLogError as exc:
            problems.append(str(exc))
    return {"ok": not problems, "problems": problems,
            "learnings": len(read_lines(learnings_path(), validate_learning)) if not problems else None,
            "active_decisions": len(active_decisions()) if not problems else None}


def _payload(argv, index):
    try:
        return json.loads(argv[index])
    except (IndexError, ValueError) as exc:
        raise MemoryLogError("expected a JSON object argument") from exc


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        command = argv[0] if argv else ""
        if command == "learn" and len(argv) == 2:
            print(json.dumps(learn(_payload(argv, 1)), ensure_ascii=False))
        elif command == "decide" and len(argv) == 2:
            print(json.dumps(decide(_payload(argv, 1)), ensure_ascii=False))
        elif command == "supersede" and len(argv) in (2, 3):
            replacement = _payload(argv, 2) if len(argv) == 3 else None
            for record in supersede(argv[1], replacement):
                print(json.dumps(record, ensure_ascii=False))
        elif command == "active" and len(argv) == 1:
            for record in active_decisions():
                print(json.dumps(record, ensure_ascii=False))
        elif command == "current" and len(argv) == 1:
            for record in current_learnings():
                print(json.dumps(record, ensure_ascii=False))
        elif command == "brief" and len(argv) == 1:
            sys.stdout.write(brief())
        elif command == "verify" and len(argv) == 1:
            result = verify()
            print(json.dumps(result))
            return 0 if result["ok"] else 1
        else:
            print(__doc__.split("\n\n")[1], file=sys.stderr)
            return 2
    except MemoryLogError as exc:
        print(f"memory_log: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
