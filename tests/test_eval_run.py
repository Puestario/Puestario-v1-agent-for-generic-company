"""evals/run.py: transparent wrapper, real fingerprints, a record score.py accepts once reviewed."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "evals/run.py"
spec = importlib.util.spec_from_file_location("scorer", ROOT / "evals/score.py")
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)
CASES = json.loads((ROOT / "evals/cases.json").read_text())
PY = sys.executable


class RunFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.records = self.dir / "records" / "trials.json"
        self.logs = self.dir / "logs"
        self.prompt = self.dir / "prompt.md"
        self.prompt.write_text("synthetic prompt v1\n")
        self.fixture = self.dir / "fixture.json"
        self.fixture.write_text('{"total": 125.0}\n')

    def run_trial(self, *extra, case="sheet_unavailable", command=None, inputs=None):
        command = command or [PY, "-c", 'print(\'{"status": "unavailable", "evidence": []}\')']
        argv = [PY, str(RUN), "--case", case, "--requested-model", "test/primary",
                "--records", str(self.records), "--log-dir", str(self.logs)]
        for path in (inputs if inputs is not None else [self.prompt, self.fixture]):
            argv += ["--input", str(path)]
        argv += list(extra) + ["--"] + command
        return subprocess.run(argv, capture_output=True, text=True)

    def record(self, index=-1):
        return json.loads(self.records.read_text())[index]


class RunTests(RunFixture):
    def test_record_carries_models_hashes_log_and_exit(self):
        run = self.run_trial("--actual-model", "test/primary", "--trial-id", "7",
                             "--tool-calls", "3", "--cost-usd", "0.02")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('"status": "unavailable"', run.stdout)
        record = self.record()
        self.assertEqual(record["case_id"], "sheet_unavailable")
        self.assertEqual(record["requested_model"], "test/primary")
        self.assertEqual(record["actual_model"], "test/primary")
        self.assertEqual(record["trial_id"], "7")
        self.assertEqual(record["tool_calls"], 3)
        self.assertEqual(record["cost_usd"], 0.02)
        self.assertEqual(record["provenance"], "runtime")
        self.assertEqual(record["final_status"], "unavailable")
        self.assertEqual(record["result"], {"status": "unavailable", "evidence": []})
        self.assertIsNone(record["fallback_reason"])
        self.assertFalse(record["fallback_disclosed"])
        self.assertFalse(record["review_passed"])
        self.assertEqual(record["reviewer"], "")
        self.assertGreaterEqual(record["latency_ms"], 0)
        for path in (self.prompt, self.fixture):
            self.assertEqual(record["input_files"][str(path)], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertTrue(record["input_fingerprint_stable"])
        log = Path(record["review_evidence"])
        self.assertTrue(log.is_file())
        self.assertEqual(log.stat().st_mode & 0o777, 0o600)
        self.assertIn('"status": "unavailable"', log.read_text())

    def test_fingerprint_is_over_file_bytes_not_names_or_git(self):
        self.run_trial("--actual-model", "test/primary")
        first = self.record()["config_revision"]
        self.run_trial("--actual-model", "test/primary")
        self.assertEqual(self.record()["config_revision"], first)
        self.prompt.write_text("synthetic prompt v2\n")
        self.run_trial("--actual-model", "test/primary")
        self.assertNotEqual(self.record()["config_revision"], first)
        self.assertEqual(len(json.loads(self.records.read_text())), 3)

    def test_exit_code_is_transparent(self):
        run = self.run_trial("--actual-model", "test/primary",
                             command=[PY, "-c", "import sys; print('boom'); sys.exit(3)"])
        self.assertEqual(run.returncode, 3)
        record = self.record()
        self.assertEqual(record["exit_code"], 3)
        self.assertEqual(record["final_status"], "failed")
        self.assertIn("no tool result JSON", run.stderr)

    def test_reviewed_record_scores_and_unreviewed_does_not(self):
        self.run_trial("--actual-model", "test/primary")
        record = self.record()
        self.assertFalse(scorer.score([record], CASES, min_trials=1)["passed"])
        reviewed = {**record, "review_passed": True, "reviewer": "human-1"}
        result = scorer.score([reviewed], CASES, min_trials=1)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["metrics"][0]["passed"], 1)

    def test_fallback_is_recorded_with_reason_and_disclosure(self):
        command = [PY, "-c", "print('actual_model=test/fallback'); print('note: running on a fallback model'); "
                             "print('{\"status\": \"succeeded\", \"evidence\": [{\"source\": \"x\", \"check\": \"report_verified\"}]}')"]
        run = self.run_trial("--fallback-reason", "primary timed out", case="fallback_disclosure", command=command)
        self.assertEqual(run.returncode, 0, run.stderr)
        record = self.record()
        self.assertEqual(record["actual_model"], "test/fallback")
        self.assertEqual(record["fallback_reason"], "primary timed out")
        self.assertTrue(record["fallback_disclosed"])
        reviewed = {**record, "review_passed": True, "reviewer": "human-1"}
        self.assertEqual(scorer.score([reviewed], CASES, min_trials=1)["failures"], [])

    def test_silent_fallback_is_not_disclosed(self):
        command = [PY, "-c", "print('{\"status\": \"unavailable\", \"evidence\": []}')"]
        run = self.run_trial("--actual-model", "test/fallback", command=command)
        self.assertIn("no --fallback-reason", run.stderr)
        record = self.record()
        self.assertFalse(record["fallback_disclosed"])
        self.assertIsNone(record["fallback_reason"])
        reviewed = {**record, "review_passed": True, "reviewer": "human-1"}
        self.assertFalse(scorer.score([reviewed], CASES, min_trials=1)["passed"])

    def test_unknown_actual_model_is_null_and_warned(self):
        run = self.run_trial()
        self.assertEqual(run.returncode, 0)
        self.assertIn("actual model unknown", run.stderr)
        self.assertIsNone(self.record()["actual_model"])

    def test_input_changed_during_run_is_flagged(self):
        command = [PY, "-c", f"open({str(self.prompt)!r}, 'a').write('edited mid-run\\n'); "
                             "print('{\"status\": \"unavailable\", \"evidence\": []}')"]
        run = self.run_trial("--actual-model", "test/primary", command=command)
        self.assertEqual(run.returncode, 0)
        self.assertIn("changed during the run", run.stderr)
        self.assertFalse(self.record()["input_fingerprint_stable"])

    def test_unknown_case_or_missing_input_refuses_to_run(self):
        marker = self.dir / "ran"
        command = [PY, "-c", f"open({str(marker)!r}, 'w').write('x')"]
        bad_case = self.run_trial("--actual-model", "test/primary", case="not_a_case", command=command)
        self.assertEqual(bad_case.returncode, 2)
        missing = self.run_trial("--actual-model", "test/primary", command=command,
                                 inputs=[self.dir / "absent.md"])
        self.assertEqual(missing.returncode, 2)
        self.assertFalse(marker.exists())
        self.assertFalse(self.records.exists())
        no_command = subprocess.run([PY, str(RUN), "--case", "sheet_unavailable", "--requested-model", "m"],
                                    capture_output=True, text=True)
        self.assertEqual(no_command.returncode, 2)

    def test_log_is_capped_with_a_marker(self):
        command = [PY, "-c", "print('x' * 5000); print('{\"status\": \"unavailable\", \"evidence\": []}')"]
        run = self.run_trial("--actual-model", "test/primary", "--log-max-bytes", "1000", command=command)
        self.assertEqual(run.returncode, 0)
        log = Path(self.record()["review_evidence"]).read_text()
        self.assertIn("log truncated", log)
        self.assertLess(len(log), 1200)
        self.assertEqual(self.record()["final_status"], "unavailable")

    def test_records_file_is_appended_not_replaced(self):
        self.records.parent.mkdir(parents=True)
        self.records.write_text(json.dumps([{"case_id": "earlier"}]))
        self.run_trial("--actual-model", "test/primary")
        records = json.loads(self.records.read_text())
        self.assertEqual([r["case_id"] for r in records], ["earlier", "sheet_unavailable"])


if __name__ == "__main__":
    unittest.main()
