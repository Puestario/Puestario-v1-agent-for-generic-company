# Tool contracts, version 1

The sales-report and WhatsApp Python adapters return a JSON-serializable object:

```json
{
  "schema_version": 1,
  "operation": "sales.report.sync",
  "status": "succeeded",
  "data": {"date": "2026-09-10", "row": 2, "counts": [4, 1], "write_attempted": true},
  "evidence": [{"source": "spreadsheet", "range": "Sheet1!G2:H2", "check": "readback_matched"}],
  "error": null
}
```

The envelope schema is in result.schema.json. Adapter data is documented below.
It is an output contract, not an OpenAI tool-registration payload.

| Status | Meaning |
|---|---|
| succeeded | Intended outcome verified by the adapter's stated check. |
| unchanged | Existing state already satisfies this operation. |
| no_record | A successful, scoped lookup returned no matching record. |
| incomplete | Input lacks information needed to complete the operation. |
| denied | A known policy or explicit provider response denied the operation. |
| unavailable | A required tool/source could not be reached or read. |
| invalid_input | Arguments or matching records are invalid or ambiguous. |
| failed | A known processing failure occurred. |
| unverified | A side effect may have happened, but completion is not confirmed. |

Evidence items may carry a `receipt`: the id of the action log line written
before the side effect (see `core/scripts/action_log.py`). An adapter that
attempts a send or a write puts that item first, so the receipt can be checked
against the log with `action_log.py verify`. An adapter that cannot write the
action line does not act; it returns `unavailable` with code
`action_log_unwritable`.

Only succeeded and unchanged are completion states. Do not use Python truthiness:
ToolResult deliberately raises on bool(result). After JSON decoding, explicitly
check status as well. Error objects contain code, a curated message and retryable
(false in these adapters). Raw subprocess commands/stderr are not returned.

## sales.report.sync

Input is the existing per-install constants; main() takes no model-supplied
arguments. It checks the date column, rejects ambiguous dates, and fills only
missing G/H counts. Zero is a real count. Incomplete reports cause no write.
Missing/unreadable session files and malformed tool responses are not "no report."

Completion requires reading both cells. Data contains date, row when found,
write_attempted, counts on completion, and reason on a scoped absence/incomplete
report. After an uncertain write it also contains reconcile_before_retry.
A queued reminder is a local file, not a delivered message.

CLI stdout is one JSON result; exit 0 means succeeded or unchanged. Every other
status exits 1, including an absent or incomplete report.

Operate one writer per sheet. Refreshing before writing reduces stale overwrites
but does not provide transaction isolation against simultaneous edits. Reconcile
unverified outcomes before rerunning. The fixed timezone offset remains a
per-install setting and must be adjusted when daylight saving changes.

## whatsapp.send

send_whatsapp(phone: str, message: str, delay: number = 4.0) accepts one recipient
and nonempty text. Delay must be finite and between 0 and 60 seconds. The existing
allowlist and authorization rules remain in force.

The desktop automation returns unverified after pressing Enter, with
send_attempted: true and message_id: null. Enter is not a delivery receipt, and
desktop focus is not proof of recipient selection. No code path claims delivery.
Check the conversation before retrying; do not automatically resend.

## Local backup

backup_local.sh remains a shell operation: exit 0 plus the published archive
means creation and archive checks completed. It writes to a staging directory,
checks gzip integrity and tar readability, then publishes and prunes old files.
Creation/check failure exits nonzero and does not prune previous backups.
Archive readability is not proof of a full application restore; restore drills
are still needed. Sources must contain all six documented entries.

## Caller migration

The old sales statuses ok/already_logged now map to succeeded/unchanged.
Errors never map to completion. The old WhatsApp boolean was removed; migrate
external callers to explicit status handling. No in-repository callers use that
old return value. Python adapters must retain access to core/scripts/tool_result.py
when deployed. These contracts do not register or configure any connectors, and
do not change who can authorize an operation.
