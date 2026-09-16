#!/usr/bin/env python3
"""
WhatsApp Outbound Sender (allowlist only)

HARD RULE: this agent never cold-messages. A number is messaged only when it
is on the allowlist file below, and a number goes on that file one of two
ways: the person has messaged the agent, or an owner has added them by
WhatsApp message from a verified owner number (core/config/reserved.md,
change 3). When an owner adds a number, the agent adds it here, in
client/identity/OWNER.md and in the channel allowlist, then confirms.

Cold outbound to numbers that never opted in is the fastest way to lose a
WhatsApp number. No warning, no appeal. When an owner asks for that anyway,
say so in the reply, then do what the owner asked. There is no bulk send in
this template on purpose.

Allowed numbers live in one file, one per line, country code, digits only.
Its path comes from the environment, in order: $WHATSAPP_ALLOWLIST, else
$OPENCLAW_STATE_DIR/whatsapp-allowlist.txt, else $HERMES_HOME/whatsapp-allowlist.txt.
With none of those set the sender returns ``unavailable`` (allowlist_path_unset)
and sends nothing.

Requires: macOS with the WhatsApp desktop app installed and running.

Every send is recorded in the action log (core/scripts/action_log.py) BEFORE
the desktop command runs, and its outcome after. If the action line cannot be
written the send does not happen. The log holds the recipient, a sha256 of the
message bytes and the byte count; never the message text.
"""

import os
import math
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import action_log
from tool_result import ToolError, error_details, outcome

def allowlist_file():
    """Resolve the allowlist path from the environment; None when nothing is set."""
    configured = os.environ.get("WHATSAPP_ALLOWLIST")
    if configured:
        return Path(configured)
    for var in ("OPENCLAW_STATE_DIR", "HERMES_HOME"):
        home = os.environ.get(var)
        if home:
            return Path(home) / "whatsapp-allowlist.txt"
    return None


def load_allowlist() -> set:
    path = allowlist_file()
    if path is None:
        raise LookupError("allowlist path unset")
    if not path.exists():
        return set()
    numbers = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        numbers.add("".join(ch for ch in line if ch.isdigit()))
    return numbers


def send_whatsapp(phone: str, message: str, delay: float = 4.0) -> dict:
    """Attempt one desktop send; this transport cannot verify delivery.

    This replaces the old boolean return. Inspect result['status'] explicitly.
    Never automatically retry an unverified attempt: it may already have sent.
    """
    operation = "whatsapp.send"
    if (not isinstance(phone, str) or not isinstance(message, str)
            or not message.strip() or isinstance(delay, bool)
            or not isinstance(delay, (int, float)) or not math.isfinite(delay)
            or not 0 <= delay <= 60):
        return outcome(operation, "invalid_input", error={
            "code": "invalid_arguments", "message": "Provide a phone, nonempty message and delay of 0–60 seconds.", "retryable": False})
    digits = "".join(ch for ch in phone if ch.isdigit())
    if not digits:
        return outcome(operation, "invalid_input", error={
            "code": "invalid_phone", "message": "The phone has no digits.", "retryable": False})
    try:
        allowed = load_allowlist()
    except LookupError:
        return outcome(operation, "unavailable", error={
            "code": "allowlist_path_unset", "message": "No allowlist path is configured; set WHATSAPP_ALLOWLIST or OPENCLAW_STATE_DIR.", "retryable": False})
    except OSError:
        return outcome(operation, "unavailable", error={
            "code": "allowlist_unreadable", "message": "The allowlist could not be read.", "retryable": False})

    if not allowed:
        return outcome(operation, "denied", error={
            "code": "allowlist_empty", "message": "No allowed numbers are configured.", "retryable": False})

    if digits not in allowed:
        return outcome(operation, "denied", error={
            "code": "recipient_not_allowed", "message": "The recipient is not on the allowlist.", "retryable": False})

    try:
        receipt = action_log.write_action(
            action=operation, target=digits, payload_class="whatsapp_message",
            payload=message.encode("utf-8"),
            consent="allowlist:" + (allowlist_file().name if allowlist_file() else "allowlist"))
    except action_log.ActionLogError:
        return outcome(operation, "unavailable", error={
            "code": "action_log_unwritable", "message": "The action log could not be written; nothing was sent.", "retryable": False})

    result = _attempt_send(operation, digits, message, delay)
    try:
        action_log.write_outcome(receipt=receipt, status=result["status"])
    except action_log.ActionLogError as exc:
        # The action line is the invariant; a missing outcome line is bookkeeping.
        print(f"whatsapp-send: warning: {exc}", file=sys.stderr)
    result["evidence"].insert(0, {"source": "action_log", "check": "receipt_written", "receipt": receipt})
    return result


def _attempt_send(operation: str, digits: str, message: str, delay: float) -> dict:
    send_attempted = False
    try:
        encoded = urllib.parse.quote(message)
        url = f"whatsapp://send?phone={digits}&text={encoded}"
        subprocess.run(["open", url], check=True, capture_output=True, text=True, timeout=30)
        time.sleep(delay)
        send_attempted = True
        subprocess.run([
            "osascript", "-e",
            'tell application "System Events" to tell process "WhatsApp" to key code 36'
        ], check=True, capture_output=True, text=True, timeout=30)
        time.sleep(2)
        return outcome(operation, "unverified", data={"send_attempted": True, "message_id": None},
                       evidence=[{"source": "desktop", "check": "enter_command_completed"}])
    except (OSError, subprocess.SubprocessError):
        # Do not echo the exception: command arguments include the message text.
        failure = ToolError("unverified" if send_attempted else "unavailable",
                            "desktop_command_failed", "The desktop command failed; check the conversation before retrying.")
        return outcome(operation, failure.status, data={"send_attempted": send_attempted, "message_id": None},
                       error=error_details(failure))


if __name__ == "__main__":
    print(__doc__)
    print(f"Allowlist file: {allowlist_file() or '(unset: WHATSAPP_ALLOWLIST / OPENCLAW_STATE_DIR / HERMES_HOME)'}")
    try:
        print(f"Numbers allowed: {len(load_allowlist())}")
    except LookupError:
        print("Numbers allowed: 0 (no allowlist path)")
