import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scorer", ROOT / "evals/score.py")
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)
CASES = json.loads((ROOT / "evals/cases.json").read_text())


def synthetic_records():
    """Fabricated unit-test inputs, never a real benchmark result."""
    records = []
    for case in CASES:
        fallback = case["id"] == "fallback_disclosure"
        records.append({
            "case_id": case["id"], "run_id": f"synthetic-{case['id']}",
            "trial_id": "1", "requested_model": "test/primary",
            "actual_model": "test/fallback" if fallback else "test/primary",
            "config_revision": "synthetic-config", "provenance": "runtime",
            "input_fingerprint_stable": True,
            "fallback_reason": "test fault" if fallback else None,
            "fallback_disclosed": fallback,
            "tool_calls": 2, "latency_ms": 100, "cost_usd": 0.01,
            "final_status": case["expected_status"],
            "result": {"status": case["expected_status"], "evidence": [
                {"source": "synthetic", "check": check} for check in case["required_checks"]]},
            "review_passed": True, "reviewer": "test-reviewer",
            "review_evidence": "synthetic-unit-test-only",
        })
    return records


class EvalTests(unittest.TestCase):
    def test_changed_or_missing_input_fingerprint_cannot_pass(self):
        for value in (False, None, "true"):
            records = synthetic_records()
            records[0]["input_fingerprint_stable"] = value
            self.assertFalse(scorer.score(records, CASES, 1)["passed"])

    def test_complete_records_score_and_measure(self):
        result = scorer.score(synthetic_records(), CASES, min_trials=1)
        self.assertTrue(result["passed"])
        self.assertEqual(sum(group["fallback_trials"] for group in result["metrics"]), 1)
        self.assertTrue(all(group["cost_per_success_usd"] == .01 for group in result["metrics"]))

    def test_empty_or_incomplete_suite_fails(self):
        for records in ([], synthetic_records()[:-1]):
            self.assertFalse(scorer.score(records, CASES, min_trials=1)["passed"])

    def test_default_requires_repeated_trials(self):
        self.assertFalse(scorer.score(synthetic_records(), CASES)["passed"])

    def test_three_distinct_trials_pass(self):
        records = []
        for index in range(3):
            for record in synthetic_records():
                record["run_id"] += f"-{index}"
                record["trial_id"] = str(index)
                records.append(record)
        self.assertTrue(scorer.score(records, CASES)["passed"])

    def test_false_success_claim_fails(self):
        records = synthetic_records()
        records[2]["final_status"] = "succeeded"
        self.assertFalse(scorer.score(records, CASES, 1)["passed"])

    def test_missing_tool_evidence_fails(self):
        records = synthetic_records()
        records[0]["result"]["evidence"] = []
        self.assertFalse(scorer.score(records, CASES, 1)["passed"])

    def test_missing_or_nonfinite_cost_is_not_zero(self):
        for cost in (None, float("nan"), float("inf"), -1, True):
            records = synthetic_records()
            records[0]["cost_usd"] = cost
            result = scorer.score(records, CASES, 1)
            self.assertFalse(result["passed"])
            primary = next(m for m in result["metrics"] if m["actual_model"] == "test/primary")
            self.assertIsNone(primary["cost_per_success_usd"])

    def test_undisclosed_fallback_fails(self):
        records = synthetic_records()
        records[-1]["fallback_disclosed"] = False
        self.assertFalse(scorer.score(records, CASES, 1)["passed"])

    def test_duplicate_trial_fails(self):
        records = synthetic_records()
        records.append(copy.deepcopy(records[0]))
        self.assertFalse(scorer.score(records, CASES, 1)["passed"])

    def test_unreviewed_or_explicitly_synthetic_records_fail(self):
        for field, value in (("review_passed", None), ("provenance", "synthetic")):
            records = synthetic_records()
            records[0][field] = value
            self.assertFalse(scorer.score(records, CASES, 1)["passed"])

    def test_failed_run_cost_is_included(self):
        records = synthetic_records()
        records[0]["review_passed"] = False
        result = scorer.score(records, CASES, 1)
        primary = next(m for m in result["metrics"] if m["actual_model"] == "test/primary")
        self.assertAlmostEqual(primary["cost_per_success_usd"], .07 / 6)

    def test_unknown_case_fails(self):
        records = synthetic_records()
        records[0]["case_id"] = "unknown"
        self.assertFalse(scorer.score(records, CASES, 1)["passed"])


if __name__ == "__main__":
    unittest.main()
