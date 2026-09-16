#!/usr/bin/env python3
"""Check yesterday's sales report; fill missing cells and verify by reading back.

Configure constants before deployment. A no-report reminder is queued locally,
not sent. Run one writer per spreadsheet: the gog CLI has no compare-and-set API.
See core/contracts/README.md for result statuses and migration from the old API.

Every spreadsheet write is recorded in the action log (core/scripts/action_log.py)
before the first cell is touched, and its outcome after the read-back. If the
action line cannot be written, nothing is written to the sheet.
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "core" / "scripts"))
import action_log
from tool_result import ToolError, error_details, outcome

SESSIONS_JSON = "YOUR_OPENCLAW_HOME/agents/YOUR_AGENT_ID/sessions/sessions.json"
GROUP_KEY = "agent:YOUR_AGENT_ID:whatsapp:group:YOUR_GROUP_ID@g.us"
SPREADSHEET_ID = "YOUR_GOOGLE_SPREADSHEET_ID"
SESSIONS_DIR = "YOUR_OPENCLAW_HOME/agents/YOUR_AGENT_ID/sessions"
REMINDER_FILE = "YOUR_OPENCLAW_HOME/workspace/tmp/sales_reminder.txt"
TIMEZONE_OFFSET = -4  # EDT; use -5 for EST
COMMAND_TIMEOUT = 30
OPERATION = "sales.report.sync"


def get_yesterday():
    tz = timezone(timedelta(hours=TIMEZONE_OFFSET))
    return (datetime.now(tz) - timedelta(days=1)).date()


def get_session_files():
    with open(SESSIONS_JSON) as source:
        sessions = json.load(source)
    group = sessions.get(GROUP_KEY)
    if not isinstance(group, dict):
        raise ToolError("unavailable", "session_missing", "The report group session is unavailable.")
    session_ids = list(group.get("usageFamilySessionIds", []))
    if group.get("sessionId") and group["sessionId"] not in session_ids:
        session_ids.append(group["sessionId"])
    if not session_ids:
        raise ToolError("unavailable", "session_missing", "No report session files were listed.")
    if any(not isinstance(sid, str) or not re.fullmatch(r"[\w-]+", sid) for sid in session_ids):
        raise ToolError("failed", "invalid_data", "The session index contains invalid identifiers.")
    return [Path(SESSIONS_DIR) / f"{sid}.jsonl" for sid in session_ids]


def message_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part["text"] for part in content
                         if isinstance(part, dict) and part.get("type") == "text"
                         and isinstance(part.get("text"), str))
    raise ToolError("failed", "invalid_data", "A message has unsupported content.")


def read_yesterdays_messages(yesterday):
    messages = []
    tz = timezone(timedelta(hours=TIMEZONE_OFFSET))
    for filepath in get_session_files():
        with open(filepath) as source:
            for line in source:
                obj = json.loads(line)
                if obj.get("type") != "message":
                    continue
                msg = obj.get("message", {})
                if msg.get("role") != "user":
                    continue
                ts = datetime.fromisoformat(obj["timestamp"].replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    raise ToolError("failed", "invalid_data", "A message timestamp has no timezone.")
                ts_local = ts.astimezone(tz)
                if ts_local.date() == yesterday:
                    messages.append({"content": message_text(msg.get("content", "")),
                                     "timestamp": ts_local})
    return sorted(messages, key=lambda msg: msg["timestamp"])


def parse_report(messages):
    reports = [m["content"] for m in messages if "reporte" in m["content"].lower()]
    if not reports:
        return None
    report = reports[-1]

    def count(labels):
        matches = re.findall(r"(?<![\w.\-])([0-9]+)\s*(?:" + labels + r")\b", report, re.I)
        if len(set(matches)) > 1:
            raise ToolError("invalid_input", "ambiguous_report", "The report has conflicting counts.")
        return int(matches[0]) if matches else None

    return count("asistidas?"), count("ventas?|cerradas?|cierres?")


def gog(*args):
    try:
        result = subprocess.run(["gog", "sheets", *args], capture_output=True,
                                text=True, timeout=COMMAND_TIMEOUT)
    except FileNotFoundError as exc:
        raise ToolError("unavailable", "tool_missing", "The gog executable is unavailable.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolError("unavailable", "timeout", "The spreadsheet command timed out.") from exc
    if result.returncode:
        # A generic CLI error is not proof of denied access or an absent record.
        raise ToolError("unavailable", "command_failed", "The spreadsheet command failed.")
    return result.stdout


def read_values(cell_range):
    try:
        payload = json.loads(gog("get", SPREADSHEET_ID, cell_range, "--json"))
        if not isinstance(payload, dict) or (
                "values" not in payload and payload.get("range") != cell_range):
            raise ValueError("Unrecognized spreadsheet response")
        values = payload.get("values", [])
        if not isinstance(values, list) or any(not isinstance(row, list) for row in values):
            raise ValueError("Invalid values")
        return values
    except (ValueError, AttributeError) as exc:
        raise ToolError("failed", "invalid_data", "The spreadsheet returned malformed data.") from exc


def get_sheet_row_for_date(target_date):
    date_str = f"{target_date.month}/{target_date.day}/{str(target_date.year)[2:]}"
    matches = [i + 1 for i, row in enumerate(read_values("Sheet1!C:C"))
               if row and row[0] == date_str]
    if len(matches) > 1:
        raise ToolError("invalid_input", "ambiguous_date", "Multiple spreadsheet rows match this date.")
    return matches[0] if matches else None


def read_counts(row):
    values = read_values(f"Sheet1!G{row}:H{row}")
    cells = values[0] if values else []
    if len(values) > 1 or len(cells) > 2:
        raise ToolError("failed", "invalid_data", "Unexpected report range dimensions.")
    counts = []
    for cell in (cells + [None, None])[:2]:
        if cell is None or (isinstance(cell, str) and not cell.strip()):
            counts.append(None)
        elif not isinstance(cell, bool) and re.fullmatch(r"[0-9]+", str(cell)):
            counts.append(int(cell))
        else:
            raise ToolError("failed", "invalid_data", "A report cell is not a nonnegative integer.")
    return counts


def queue_reminder(message):
    # Only a local file. The existing install controls whether/how it is delivered.
    Path(REMINDER_FILE).write_text(message + "\n")


def main():
    state = {"receipt": None}
    result = _main(state)
    if state["receipt"]:
        try:
            action_log.write_outcome(receipt=state["receipt"], status=result["status"])
        except action_log.ActionLogError as exc:
            # The action line is the invariant; a missing outcome line is bookkeeping.
            print(f"ventas_report_check: warning: {exc}", file=sys.stderr)
        result["evidence"].insert(0, {"source": "action_log", "check": "receipt_written",
                                      "receipt": state["receipt"]})
    return result


def _main(state):
    yesterday = get_yesterday()
    data = {"date": str(yesterday), "write_attempted": False}
    evidence = []
    try:
        row = get_sheet_row_for_date(yesterday)
        evidence.append({"source": "spreadsheet", "range": "Sheet1!C:C", "check": "read"})
        if row is None:
            return outcome(OPERATION, "no_record", data={**data, "reason": "date_row_absent"}, evidence=evidence)
        data["row"] = row
        current = read_counts(row)
        evidence.append({"source": "spreadsheet", "range": f"Sheet1!G{row}:H{row}", "check": "read"})
        if all(value is not None for value in current):
            return outcome(OPERATION, "unchanged", data={**data, "counts": current}, evidence=evidence)

        report = parse_report(read_yesterdays_messages(yesterday))
        if report is None:
            queue_reminder(f"Reminder: No report received for {yesterday.strftime('%d/%m')}. Please send your daily report.")
            evidence.append({"source": "local_reminder_file", "check": "written"})
            return outcome(OPERATION, "no_record", data={**data, "reason": "report_absent", "reminder_queued": True}, evidence=evidence)
        # Refresh immediately before writing. Preserve filled cells, including zero.
        current = read_counts(row)
        desired = [old if old is not None else new for old, new in zip(current, report)]
        if any(value is None for value in desired):
            return outcome(OPERATION, "incomplete", data={**data, "reason": "missing_count"}, evidence=evidence)
        pending = [(column, new) for column, old, new in zip("GH", current, desired) if old is None]
        if not pending:
            return outcome(OPERATION, "unchanged", data={**data, "counts": current}, evidence=evidence)
        try:
            state["receipt"] = action_log.write_action(
                action=OPERATION, target=f"spreadsheet:{SPREADSHEET_ID}:Sheet1!G{row}:H{row}",
                payload_class="report_counts", consent="cron:" + OPERATION,
                payload=json.dumps(dict(pending)).encode("utf-8"))
        except action_log.ActionLogError as exc:
            raise ToolError("unavailable", "action_log_unwritable",
                            "The action log could not be written; nothing was written to the sheet.") from exc
        for column, new in pending:
            data["write_attempted"] = True
            gog("update", SPREADSHEET_ID, f"Sheet1!{column}{row}", str(new))
        actual = read_counts(row)
        if actual != desired:
            raise ToolError("unverified", "readback_mismatch", "The stored report does not match the intended result.")
        evidence.append({"source": "spreadsheet", "range": f"Sheet1!G{row}:H{row}", "check": "readback_matched"})
        return outcome(OPERATION, "succeeded" if data["write_attempted"] else "unchanged",
                       data={**data, "counts": actual}, evidence=evidence)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        failure = ToolError("unavailable" if isinstance(exc, OSError) else "failed",
                            "source_unreadable", "A required local report source could not be read or parsed.")
    except ToolError as exc:
        failure = exc
    if data["write_attempted"]:
        data["reconcile_before_retry"] = True
    return outcome(OPERATION, "unverified" if data["write_attempted"] else failure.status,
                   data=data, evidence=evidence, error=error_details(failure))


if __name__ == "__main__":
    result = main()
    print(json.dumps(result))
    sys.exit(0 if result["status"] in {"succeeded", "unchanged"} else 1)
