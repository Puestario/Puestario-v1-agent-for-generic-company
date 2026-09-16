"""Action log: chain holds when untouched, breaks on any edit, gates every side effect."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "scripts"))
import action_log  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reply(values=None, *, returncode=0):
    return subprocess.CompletedProcess([], returncode, json.dumps({"values": values or []}), "")


class LogFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log = Path(self.temp.name) / "security" / "action-log.jsonl"
        patcher = patch.dict(os.environ, {"ACTION_LOG": str(self.log)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def lines(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def action(self, n=1, payload=b"synthetic payload"):
        return action_log.write_action(action="test.send", target=f"target-{n}",
                                       payload_class="synthetic", consent="test", payload=payload)


class ChainTests(LogFixture):
    def test_empty_or_missing_log_verifies(self):
        self.assertEqual(action_log.verify()["ok"], True)
        self.assertEqual(action_log.verify()["count"], 0)

    def test_lines_chain_and_verify(self):
        first = self.action(1)
        action_log.write_outcome(receipt=first, status="unverified")
        second = self.action(2)
        raw = self.log.read_text().splitlines()
        records = self.lines()
        self.assertEqual(records[0]["prev"], "")
        self.assertEqual(records[1]["prev"], action_log.sha256_hex(raw[0]))
        self.assertEqual(records[2]["prev"], action_log.sha256_hex(raw[1]))
        self.assertEqual(first, action_log.sha256_hex(raw[0]))
        self.assertNotEqual(first, second)
        self.assertEqual(action_log.verify(), {"ok": True, "count": 3, "broken_line": None, "reason": None})

    def test_content_free_but_provable(self):
        self.action(payload=b"SENSITIVE message body")
        record = self.lines()[0]
        self.assertNotIn("SENSITIVE", self.log.read_text())
        self.assertEqual(record["bytes"], len(b"SENSITIVE message body"))
        self.assertEqual(record["sha256"], action_log.sha256_hex(b"SENSITIVE message body"))

    def test_outcome_joins_to_its_action(self):
        first = self.action(1)
        self.action(2)
        action_log.write_outcome(receipt=first, status="unverified")
        listed = action_log.list_actions()
        self.assertEqual([entry["status"] for entry in listed], ["unverified", None])
        self.assertEqual(listed[0]["id"], first)

    def test_edited_line_breaks_the_chain(self):
        self.action(1)
        self.action(2)
        self.action(3)
        raw = self.log.read_text().splitlines()
        raw[1] = raw[1].replace("target-2", "target-9")
        self.log.write_text("\n".join(raw) + "\n")
        result = action_log.verify()
        self.assertFalse(result["ok"])
        self.assertEqual(result["broken_line"], 3)

    def test_deleted_line_breaks_the_chain(self):
        self.action(1)
        self.action(2)
        self.action(3)
        raw = self.log.read_text().splitlines()
        del raw[1]
        self.log.write_text("\n".join(raw) + "\n")
        self.assertEqual(action_log.verify()["broken_line"], 2)

    def test_inserted_line_breaks_the_chain(self):
        self.action(1)
        self.action(2)
        raw = self.log.read_text().splitlines()
        forged = json.dumps({"ts": "2026-01-01T00:00:00Z", "type": "action", "action": "forged",
                             "prev": action_log.sha256_hex(raw[0])})
        self.log.write_text("\n".join([raw[0], forged, raw[1]]) + "\n")
        self.assertEqual(action_log.verify()["broken_line"], 3)

    def test_truncated_tail_breaks_the_chain(self):
        self.action(1)
        self.action(2)
        raw = self.log.read_text().splitlines()
        self.log.write_text(raw[0] + "\n")
        # Removing the last line leaves a valid shorter chain: the log cannot
        # prove its own length. That is the documented limit, not a bug.
        self.assertTrue(action_log.verify()["ok"])
        self.assertEqual(action_log.verify()["count"], 1)

    def test_garbage_line_is_reported(self):
        self.action(1)
        with open(self.log, "a") as handle:
            handle.write("not json\n")
        result = action_log.verify()
        self.assertFalse(result["ok"])
        self.assertEqual(result["broken_line"], 2)
        self.assertEqual(result["reason"], "unparseable or missing prev")

    def test_file_is_private(self):
        self.action(1)
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.log.parent.stat().st_mode & 0o777, 0o700)

    def test_fields_are_validated(self):
        for kwargs in ({"action": ""}, {"target": "a\nb"}, {"consent": "x" * 600}, {"payload": "text"}):
            with self.subTest(kwargs=kwargs):
                base = {"action": "a", "target": "t", "payload_class": "p", "consent": "c"}
                base.update(kwargs)
                with self.assertRaises(action_log.ActionLogError):
                    action_log.write_action(**base)
        with self.assertRaises(action_log.ActionLogError):
            action_log.write_outcome(receipt="not-a-hash", status="x")
        self.assertFalse(self.log.exists())

    def test_unwritable_location_raises(self):
        blocker = Path(self.temp.name) / "blocker"
        blocker.write_text("a file where the directory should be")
        with patch.dict(os.environ, {"ACTION_LOG": str(blocker / "log.jsonl")}):
            with self.assertRaises(action_log.ActionLogError):
                self.action(1)

    def test_stale_lock_is_reclaimed_and_live_lock_is_respected(self):
        lock = Path(str(self.log) + ".lock")
        lock.parent.mkdir(parents=True)
        lock.mkdir()
        old = 1_000_000_000
        os.utime(lock, (old, old))
        with patch.object(action_log, "LOCK_BUDGET_SECONDS", 0.05):
            self.action(1)
        self.assertTrue(action_log.verify()["ok"])
        lock.mkdir()
        with patch.object(action_log, "LOCK_BUDGET_SECONDS", 0.05):
            with self.assertRaises(action_log.ActionLogError):
                self.action(2)

    def test_cli_verify_exits_nonzero_on_tamper(self):
        self.action(1)
        self.action(2)
        script = ROOT / "core/scripts/action_log.py"
        ok = subprocess.run([sys.executable, str(script), "verify", "--path", str(self.log)], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertTrue(json.loads(ok.stdout)["ok"])
        raw = self.log.read_text().splitlines()
        self.log.write_text(raw[0].replace("target-1", "target-0") + "\n" + raw[1] + "\n")
        bad = subprocess.run([sys.executable, str(script), "verify", "--path", str(self.log)], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertFalse(json.loads(bad.stdout)["ok"])
        usage = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        self.assertEqual(usage.returncode, 2)


class PathAndCliTests(LogFixture):
    def test_path_comes_from_env_in_order_and_never_from_home(self):
        with patch.dict(os.environ, {"ACTION_LOG": "/x/explicit.jsonl", "OPENCLAW_STATE_DIR": "/x/state"}):
            self.assertEqual(str(action_log.default_path()), "/x/explicit.jsonl")
        env = {k: v for k, v in os.environ.items() if k not in ("ACTION_LOG", "OPENCLAW_STATE_DIR", "HERMES_HOME")}
        with patch.dict(os.environ, {**env, "OPENCLAW_STATE_DIR": "/x/state"}, clear=True):
            self.assertEqual(str(action_log.default_path()), "/x/state/security/action-log.jsonl")
        with patch.dict(os.environ, {**env, "HERMES_HOME": "/x/hermes"}, clear=True):
            self.assertEqual(str(action_log.default_path()), "/x/hermes/security/action-log.jsonl")
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(action_log.ActionLogError):
                action_log.default_path()
            with self.assertRaises(action_log.ActionLogError):
                self.action(1)
            self.assertEqual(action_log.verify(), {"ok": True, "count": 0, "broken_line": None, "reason": None})
        self.assertNotIn(".openclaw", Path(action_log.__file__).read_text().replace("OPENCLAW_STATE_DIR", ""))

    def test_record_and_outcome_cli(self):
        script = str(ROOT / "core/scripts/action_log.py")
        rec = subprocess.run([sys.executable, script, "record", "--action", "whatsapp.send", "--target", "15555550100",
                              "--payload-class", "message", "--consent", "openclaw:test", "--payload-stdin"],
                             input=b"SENSITIVE body", capture_output=True)
        self.assertEqual(rec.returncode, 0, rec.stderr)
        receipt = rec.stdout.decode().strip()
        self.assertRegex(receipt, r"^[0-9a-f]{64}$")
        out = subprocess.run([sys.executable, script, "outcome", "--receipt", receipt, "--status", "sent"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        records = self.lines()
        self.assertEqual([r["type"] for r in records], ["action", "outcome"])
        self.assertEqual(records[0]["sha256"], action_log.sha256_hex(b"SENSITIVE body"))
        self.assertEqual(records[1]["receipt"], receipt)
        self.assertNotIn("SENSITIVE", self.log.read_text())
        self.assertTrue(action_log.verify()["ok"])

    def test_record_cli_fails_when_unconfigured_or_unwritable(self):
        script = str(ROOT / "core/scripts/action_log.py")
        env = {k: v for k, v in os.environ.items() if k not in ("ACTION_LOG", "OPENCLAW_STATE_DIR", "HERMES_HOME")}
        unset = subprocess.run([sys.executable, script, "record", "--action", "a", "--target", "t",
                                "--payload-class", "p", "--consent", "c"], capture_output=True, text=True, env=env)
        self.assertEqual(unset.returncode, 1)
        self.assertIn("no action log path", unset.stderr)
        blocker = Path(self.temp.name) / "blocker"
        blocker.write_text("")
        bad = subprocess.run([sys.executable, script, "record", "--action", "a", "--target", "t",
                              "--payload-class", "p", "--consent", "c"], capture_output=True, text=True,
                             env={**os.environ, "ACTION_LOG": str(blocker / "log.jsonl")})
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(bad.stdout, "")


class WhatsAppLogTests(LogFixture):
    def setUp(self):
        super().setUp()
        self.whatsapp = load("whatsapp_logged", "core/scripts/whatsapp-send.py")

    def attempt(self, phone="15555550100", responses=None):
        with patch.object(self.whatsapp, "load_allowlist", return_value={"15555550100"}), \
             patch.object(self.whatsapp.subprocess, "run", side_effect=responses) as command, \
             patch.object(self.whatsapp.time, "sleep"):
            result = self.whatsapp.send_whatsapp(phone, "SENSITIVE synthetic message", 0)
        return result, command

    def test_send_writes_action_then_outcome(self):
        result, command = self.attempt()
        self.assertEqual(command.call_count, 2)
        records = self.lines()
        self.assertEqual([r["type"] for r in records], ["action", "outcome"])
        self.assertEqual(records[0]["action"], "whatsapp.send")
        self.assertEqual(records[0]["target"], "15555550100")
        self.assertEqual(records[1]["status"], "unverified")
        self.assertEqual(result["evidence"][0]["check"], "receipt_written")
        self.assertEqual(result["evidence"][0]["receipt"], records[1]["receipt"])
        self.assertNotIn("SENSITIVE", self.log.read_text())
        self.assertTrue(action_log.verify()["ok"])

    def test_unset_allowlist_path_is_unavailable_not_denied(self):
        env = {k: v for k, v in os.environ.items() if k not in ("WHATSAPP_ALLOWLIST", "OPENCLAW_STATE_DIR", "HERMES_HOME")}
        with patch.dict(os.environ, env, clear=True), \
             patch.object(self.whatsapp.subprocess, "run") as command:
            result = self.whatsapp.send_whatsapp("15555550100", "hello", 0)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["error"]["code"], "allowlist_path_unset")
        command.assert_not_called()
        with patch.dict(os.environ, {**env, "OPENCLAW_STATE_DIR": "/x/state"}, clear=True):
            self.assertEqual(str(self.whatsapp.allowlist_file()), "/x/state/whatsapp-allowlist.txt")

    def test_denied_send_is_not_an_action(self):
        result, command = self.attempt(phone="15555550999")
        self.assertEqual(result["status"], "denied")
        command.assert_not_called()
        self.assertFalse(self.log.exists())

    def test_unwritable_log_blocks_the_send(self):
        blocker = Path(self.temp.name) / "blocker"
        blocker.write_text("")
        with patch.dict(os.environ, {"ACTION_LOG": str(blocker / "log.jsonl")}):
            result, command = self.attempt()
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["error"]["code"], "action_log_unwritable")
        command.assert_not_called()

    def test_failed_desktop_command_still_gets_an_outcome(self):
        result, _ = self.attempt(responses=[FileNotFoundError()])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual([r["type"] for r in self.lines()], ["action", "outcome"])
        self.assertEqual(self.lines()[1]["status"], "unavailable")


class SalesLogTests(LogFixture):
    def setUp(self):
        super().setUp()
        self.sales = load("sales_logged", "client/scripts/ventas_report_check.py")

    def run_report(self, responses):
        with patch.object(self.sales, "get_yesterday", return_value=date(2026, 9, 10)), \
             patch.object(self.sales, "read_yesterdays_messages",
                          return_value=[{"content": "reporte 4 asistidas 1 venta"}]), \
             patch.object(self.sales, "queue_reminder"), \
             patch.object(self.sales.subprocess, "run", side_effect=responses) as command:
            result = self.sales.main()
        return result, [call.args[0] for call in command.call_args_list if call.args[0][2] == "update"]

    def test_write_is_logged_before_and_after(self):
        result, updates = self.run_report([
            reply([["9/10/26"]]), reply([[4]]), reply([[4]]), reply(), reply([[4, 1]])])
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(updates), 1)
        records = self.lines()
        self.assertEqual([r["type"] for r in records], ["action", "outcome"])
        self.assertEqual(records[0]["action"], "sales.report.sync")
        self.assertEqual(records[0]["sha256"], action_log.sha256_hex(json.dumps({"H": 1}).encode()))
        self.assertEqual(records[1]["status"], "succeeded")
        self.assertEqual(result["evidence"][0]["check"], "receipt_written")
        self.assertEqual(result["evidence"][-1]["check"], "readback_matched")

    def test_unchanged_row_writes_nothing_to_the_log(self):
        result, updates = self.run_report([reply([["9/10/26"]]), reply([[0, "0"]])])
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(updates, [])
        self.assertFalse(self.log.exists())

    def test_unwritable_log_blocks_the_sheet_write(self):
        blocker = Path(self.temp.name) / "blocker"
        blocker.write_text("")
        with patch.dict(os.environ, {"ACTION_LOG": str(blocker / "log.jsonl")}):
            result, updates = self.run_report([
                reply([["9/10/26"]]), reply([[4]]), reply([[4]]), reply(), reply([[4, 1]])])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["error"]["code"], "action_log_unwritable")
        self.assertEqual(updates, [])
        self.assertFalse(result["data"]["write_attempted"])

    def test_failed_write_outcome_is_unverified(self):
        result, updates = self.run_report([
            reply([["9/10/26"]]), reply(), reply(), reply(), reply(returncode=1)])
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(self.lines()[-1]["status"], "unverified")


if __name__ == "__main__":
    unittest.main()
