import importlib.util
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "scripts"))

# Adapters append to the action log on every attempted side effect. Keep the
# tests' log out of the developer's real one.
_LOG_DIR = tempfile.TemporaryDirectory()
os.environ["ACTION_LOG"] = str(Path(_LOG_DIR.name) / "action-log.jsonl")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sales = load("sales", "client/scripts/ventas_report_check.py")
whatsapp = load("whatsapp", "core/scripts/whatsapp-send.py")
from tool_result import ToolError, outcome


def reply(values=None, *, returncode=0, stdout=None):
    return subprocess.CompletedProcess([], returncode,
                                       json.dumps({"values": values or []}) if stdout is None else stdout,
                                       "SENSITIVE_PROVIDER_OUTPUT")


class SalesTests(unittest.TestCase):
    def run_report(self, responses, text="reporte 4 asistidas 1 venta"):
        with patch.object(sales, "get_yesterday", return_value=date(2026, 9, 10)), \
             patch.object(sales, "read_yesterdays_messages", return_value=[{"content": text}]), \
             patch.object(sales, "queue_reminder") as reminder, \
             patch.object(sales.subprocess, "run", side_effect=responses) as command:
            result = sales.main()
        return result, command.call_args_list, reminder

    def updates(self, calls):
        return [call.args[0] for call in calls if call.args[0][2] == "update"]

    def test_partial_row_repairs_only_missing_cell(self):
        result, calls, _ = self.run_report([
            reply([["9/10/26"]]), reply([[4]]), reply([[4]]), reply(), reply([[4, 1]])])
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual([call[-2:] for call in self.updates(calls)], [["Sheet1!H1", "1"]])
        self.assertEqual(result["evidence"][-1]["check"], "readback_matched")

    def test_complete_zero_counts_are_unchanged(self):
        result, calls, _ = self.run_report([reply([["9/10/26"]]), reply([[0, "0"]])])
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(self.updates(calls), [])

    def test_existing_manual_number_is_preserved(self):
        result, calls, _ = self.run_report([
            reply([["9/10/26"]]), reply([[9]]), reply([[9]]), reply(), reply([[9, 1]])])
        self.assertEqual(result["data"]["counts"], [9, 1])
        self.assertEqual([call[-2:] for call in self.updates(calls)], [["Sheet1!H1", "1"]])

    def test_fresh_read_preserves_newly_filled_cell(self):
        result, calls, _ = self.run_report([
            reply([["9/10/26"]]), reply(), reply([[7, 2]]), reply([[7, 2]])])
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(self.updates(calls), [])

    def test_fresh_report_writes_and_reads_both_counts(self):
        result, calls, _ = self.run_report([
            reply([["9/10/26"]]), reply(), reply(), reply(), reply(), reply([[4, 1]])])
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(self.updates(calls)), 2)

    def test_read_failure_is_not_an_absent_report(self):
        result, calls, reminder = self.run_report([reply(returncode=1)])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.updates(calls), [])
        reminder.assert_not_called()
        self.assertNotIn("SENSITIVE", json.dumps(result))

    def test_missing_date_is_scoped_absence(self):
        result, calls, reminder = self.run_report([reply([["9/9/26"]])])
        self.assertEqual(result["status"], "no_record")
        self.assertEqual(result["data"]["reason"], "date_row_absent")
        reminder.assert_not_called()

    def test_duplicate_date_prevents_write(self):
        result, calls, _ = self.run_report([reply([["9/10/26"], ["9/10/26"]])])
        self.assertEqual(result["status"], "invalid_input")
        self.assertEqual(self.updates(calls), [])

    def test_write_error_never_reports_success(self):
        result, calls, _ = self.run_report([
            reply([["9/10/26"]]), reply(), reply(), reply(), reply(returncode=1)])
        self.assertEqual(result["status"], "unverified")
        self.assertTrue(result["data"]["reconcile_before_retry"])
        self.assertEqual(len(self.updates(calls)), 2)
        self.assertNotIn("SENSITIVE", json.dumps(result))

    def test_timeout_after_attempt_requires_reconciliation(self):
        result, calls, _ = self.run_report([
            reply([["9/10/26"]]), reply(), reply(),
            subprocess.TimeoutExpired("gog", 30)])
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(len(self.updates(calls)), 1)

    def test_missing_cli_is_unavailable(self):
        result, _, _ = self.run_report([FileNotFoundError()])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["error"]["code"], "tool_missing")

    def test_readback_mismatch_is_unverified(self):
        result, _, _ = self.run_report([
            reply([["9/10/26"]]), reply([[4]]), reply([[4]]), reply(), reply([[4, 0]])])
        self.assertEqual(result["status"], "unverified")

    def test_invalid_json_is_not_absence(self):
        result, _, _ = self.run_report([reply(stdout="not json")])
        self.assertEqual(result["status"], "failed")

    def test_error_shaped_json_is_not_an_empty_sheet(self):
        result, _, _ = self.run_report([reply(stdout='{"error":"permission denied"}')])
        self.assertEqual(result["status"], "failed")

    def test_explicit_empty_range_is_a_scoped_absence(self):
        result, _, _ = self.run_report([reply(stdout='{"range":"Sheet1!C:C"}')])
        self.assertEqual(result["status"], "no_record")

    def test_invalid_cell_does_not_get_overwritten(self):
        result, calls, _ = self.run_report([reply([["9/10/26"]]), reply([["N/A", ""]])])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.updates(calls), [])

    def test_incomplete_report_does_not_write(self):
        result, calls, _ = self.run_report([
            reply([["9/10/26"]]), reply(), reply()], "reporte: 4 asistidas; cierres pendientes")
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(self.updates(calls), [])

    def test_no_report_queues_local_reminder_only(self):
        result, calls, reminder = self.run_report([reply([["9/10/26"]]), reply()], "hola")
        self.assertEqual(result["status"], "no_record")
        self.assertTrue(result["data"]["reminder_queued"])
        reminder.assert_called_once()
        self.assertEqual(self.updates(calls), [])

    def test_closes_alternation_requires_a_count(self):
        self.assertEqual(sales.parse_report([{"content": "reporte: cierres pendientes"}]), (None, None))
        self.assertEqual(sales.parse_report([{"content": "reporte: 2 cierres"}]), (None, 2))

    def test_negative_and_decimal_counts_are_not_silently_reinterpreted(self):
        for text in ("reporte -12 ventas", "reporte 1.5 ventas"):
            with self.subTest(text=text):
                self.assertEqual(sales.parse_report([{"content": text}]), (None, None))

    def test_conflicting_counts_rejected(self):
        with self.assertRaises(ToolError):
            sales.parse_report([{"content": "reporte 2 ventas 3 cierres"}])

    def test_missing_session_does_not_queue_a_reminder(self):
        with patch.object(sales, "get_yesterday", return_value=date(2026, 9, 10)), \
             patch.object(sales, "get_sheet_row_for_date", return_value=1), \
             patch.object(sales, "read_counts", return_value=[None, None]), \
             patch.object(sales, "get_session_files", return_value=[Path("/missing/synthetic-session.jsonl")]), \
             patch.object(sales, "queue_reminder") as reminder:
            result = sales.main()
        self.assertEqual(result["status"], "unavailable")
        reminder.assert_not_called()

    def test_structured_messages_and_cross_session_order(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for i, hour in enumerate((19, 12)):
                path = Path(directory) / f"{i}.jsonl"
                path.write_text(json.dumps({"type": "message",
                    "timestamp": f"2026-09-10T{hour}:00:00Z",
                    "message": {"role": "user", "content": [
                        {"type": "text", "text": f"reporte {i + 1} ventas"}]}}) + "\n")
                paths.append(path)
            with patch.object(sales, "get_session_files", return_value=paths):
                messages = sales.read_yesterdays_messages(date(2026, 9, 10))
        self.assertEqual(sales.parse_report(messages), (None, 1))

    def test_cli_failure_exits_nonzero_with_json(self):
        # Unconfigured template only; no external call can run without the mocked PATH.
        with tempfile.TemporaryDirectory() as directory:
            env = {**os.environ, "PATH": directory}
            result = subprocess.run([sys.executable, str(ROOT / "client/scripts/ventas_report_check.py")],
                                    capture_output=True, text=True, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["status"], "unavailable")


class WhatsAppTests(unittest.TestCase):
    def attempt(self, responses=None, allowed=None, **kwargs):
        with patch.object(whatsapp, "load_allowlist", return_value={"15555550100"} if allowed is None else allowed), \
             patch.object(whatsapp.subprocess, "run", side_effect=responses) as command, \
             patch.object(whatsapp.time, "sleep"):
            result = whatsapp.send_whatsapp(kwargs.get("phone", "15555550100"),
                                            kwargs.get("message", "synthetic message"),
                                            kwargs.get("delay", 0))
        return result, command

    def test_desktop_success_is_unverified(self):
        result, command = self.attempt()
        self.assertEqual(result["status"], "unverified")
        self.assertIsNone(result["data"]["message_id"])
        self.assertEqual(command.call_count, 2)
        with self.assertRaises(TypeError):
            bool(result)

    def test_nonallowlisted_recipient_is_blocked(self):
        result, command = self.attempt(phone="15555550999")
        self.assertEqual(result["status"], "denied")
        command.assert_not_called()

    def test_empty_allowlist_blocks(self):
        result, command = self.attempt(allowed=set())
        self.assertEqual(result["status"], "denied")
        command.assert_not_called()

    def test_invalid_arguments_never_run_a_command(self):
        for args in ({"phone": None}, {"phone": "abc"}, {"message": ""},
                     {"delay": -1}, {"delay": float("nan")}, {"delay": True}):
            with self.subTest(args=args):
                result, command = self.attempt(**args)
                self.assertEqual(result["status"], "invalid_input")
                command.assert_not_called()

    def test_failed_enter_has_no_automatic_retry_or_message_leak(self):
        result, command = self.attempt(responses=[
            reply(), subprocess.CalledProcessError(1, ["osascript", "SENSITIVE_MESSAGE"])])
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(command.call_count, 2)
        self.assertNotIn("SENSITIVE", json.dumps(result))

    def test_missing_desktop_command_is_unavailable(self):
        result, command = self.attempt(responses=[FileNotFoundError()])
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["data"]["send_attempted"])
        self.assertEqual(command.call_count, 1)


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "agent home"
        self.backups = self.root / "backups"
        self.home.mkdir()
        self.backups.mkdir()
        (self.home / "openclaw.json").write_text("{}")
        for name in ("workspace", "state", "credentials", "secrets", "agents"):
            (self.home / name).mkdir()
            (self.home / name / "synthetic.txt").write_text("synthetic test data")
        self.old = self.backups / "agent-backup-old.tar.gz"
        self.old.write_text("previous archive sentinel")
        old_time = time.time() - 30 * 86400
        os.utime(self.old, (old_time, old_time))

    def run_backup(self, **extra):
        env = {**os.environ, "OPENCLAW_HOME": str(self.home),
               "BACKUP_DIR": str(self.backups), "KEEP_DAYS": "14", **extra}
        return subprocess.run(["/bin/bash", str(ROOT / "client/scripts/backup_local.sh")],
                              env=env, capture_output=True, text=True)

    def test_success_is_readable_and_retains_documented_sources(self):
        result = self.run_backup()
        self.assertEqual(result.returncode, 0, result.stderr)
        archives = list(self.backups.glob("agent-backup-*.tar.gz"))
        self.assertEqual(len(archives), 1)
        with tarfile.open(archives[0]) as archive:
            names = archive.getnames()
            self.assertIn("credentials/synthetic.txt", names)
            self.assertIn("secrets/synthetic.txt", names)
            self.assertEqual(archive.extractfile("workspace/synthetic.txt").read(), b"synthetic test data")
        self.assertFalse(self.old.exists())
        self.assertEqual(list(self.backups.glob(".agent-backup.*")), [])

    def test_creation_failure_preserves_previous_backup(self):
        (self.home / "openclaw.json").unlink()
        result = self.run_backup()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.old.exists())
        self.assertNotIn("Done:", result.stdout)
        self.assertEqual(list(self.backups.glob("agent-backup-*.tar.gz")), [self.old])
        self.assertEqual(list(self.backups.glob(".agent-backup.*")), [])

    def test_invalid_archive_from_successful_tar_is_rejected(self):
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        fake_tar = bin_dir / "tar"
        fake_tar.write_text('#!/bin/sh\nif [ "$1" = "-czf" ]; then printf broken > "$2"; fi\nexit 0\n')
        fake_tar.chmod(0o755)
        result = self.run_backup(PATH=str(bin_dir) + os.pathsep + os.environ["PATH"])
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.old.exists())
        self.assertEqual(list(self.backups.glob("agent-backup-*.tar.gz")), [self.old])

    def test_retention_does_not_descend_into_subdirectories(self):
        nested = self.backups / "other"
        nested.mkdir()
        sentinel = nested / "agent-backup-other.tar.gz"
        sentinel.write_text("preserve")
        old_time = time.time() - 30 * 86400
        os.utime(sentinel, (old_time, old_time))
        self.assertEqual(self.run_backup().returncode, 0)
        self.assertTrue(sentinel.exists())

    def test_invalid_retention_fails_before_pruning(self):
        self.assertNotEqual(self.run_backup(KEEP_DAYS="-1").returncode, 0)
        self.assertTrue(self.old.exists())

    def test_destination_inside_source_is_rejected(self):
        self.assertNotEqual(self.run_backup(BACKUP_DIR=str(self.home / "workspace" / "backups")).returncode, 0)
        self.assertTrue(self.old.exists())


class ContractTests(unittest.TestCase):
    def test_success_requires_evidence(self):
        with self.assertRaises(ValueError):
            outcome("test", "succeeded")

    def test_unknown_status_rejected(self):
        with self.assertRaises(ValueError):
            outcome("test", "ok")

    def test_schema_and_runtime_statuses_agree(self):
        from tool_result import STATUSES
        schema = json.loads((ROOT / "core/contracts/result.schema.json").read_text())
        self.assertEqual(set(schema["properties"]["status"]["enum"]), STATUSES)
        result = outcome("test", "unavailable")
        self.assertEqual(set(result), set(schema["required"]))


if __name__ == "__main__":
    unittest.main()
