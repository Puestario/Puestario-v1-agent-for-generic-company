#!/usr/bin/env python3
"""Score sanitized agent trial records offline; never calls a model or a connector."""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

CASES = Path(__file__).with_name("cases.json")


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def grade(record, case):
    errors = []
    for field in ("run_id", "trial_id", "requested_model", "actual_model", "config_revision",
                  "reviewer", "review_evidence"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            errors.append(f"missing {field}")
    for field in ("latency_ms", "cost_usd", "tool_calls"):
        if not number(record.get(field)):
            errors.append(f"invalid {field}")
    if number(record.get("tool_calls")) and not isinstance(record["tool_calls"], int):
        errors.append("tool_calls must be an integer")
    if record.get("provenance") != "runtime":
        errors.append("not a runtime trial")
    if record.get("input_fingerprint_stable") is not True:
        errors.append("input fingerprint changed or was not verified")
    if record.get("review_passed") is not True:
        errors.append("human outcome review not passed")
    if record.get("final_status") != case["expected_status"]:
        errors.append("incorrect final status")
    result = record.get("result", {})
    if not isinstance(result, dict):
        result = {}
    if result.get("status") != case["expected_status"]:
        errors.append("incorrect observed outcome")
    evidence = result.get("evidence", [])
    checks = {item.get("check") for item in evidence if isinstance(item, dict)} if isinstance(evidence, list) else set()
    if not set(case["required_checks"]).issubset(checks):
        errors.append("required tool evidence missing")
    fallback = record.get("actual_model") != record.get("requested_model")
    if case["id"] == "fallback_disclosure" and not fallback:
        errors.append("fallback case did not exercise fallback")
    if fallback and (not isinstance(record.get("fallback_reason"), str)
                     or not record["fallback_reason"].strip()
                     or record.get("fallback_disclosed") is not True):
        errors.append("fallback reason or disclosure missing")
    return errors


def score(records, cases, min_trials=3):
    if not isinstance(min_trials, int) or min_trials < 1:
        raise ValueError("min_trials must be a positive integer")
    if not isinstance(records, list) or not isinstance(cases, list) or not cases:
        raise ValueError("Provide a list of records and a nonempty case list")
    case_map = {case["id"]: case for case in cases}
    seen, run_ids = set(), set()
    counts = defaultdict(int)
    groups = defaultdict(list)
    failures = []
    for index, record in enumerate(records):
        if not isinstance(record, dict) or record.get("case_id") not in case_map:
            failures.append({"record": index, "errors": ["unknown or missing case"]})
            continue
        case_id = record["case_id"]
        trial = record.get("trial_id")
        requested = record.get("requested_model")
        actual = record.get("actual_model")
        # Invalid/missing IDs are graded but cannot count toward coverage.
        key = (case_id, str(trial), str(requested))
        errors = grade(record, case_map[case_id])
        if key in seen or str(record.get("run_id")) in run_ids:
            errors.append("duplicate trial or run ID")
        else:
            counts[(str(requested), case_id)] += 1
        seen.add(key)
        run_ids.add(str(record.get("run_id")))
        if errors:
            failures.append({"record": index, "case_id": case_id, "errors": errors})
        groups[(str(requested), str(actual))].append((record, not errors))
    requested_models = {requested for requested, _ in groups}
    missing = [f"{model}/{case_id}: {counts[(model, case_id)]}/{min_trials}"
               for model in sorted(requested_models) for case_id in case_map
               if counts[(model, case_id)] < min_trials]
    if not records or not requested_models:
        missing.append("no runtime trials")
    metrics = []
    for (requested, actual), runs in sorted(groups.items()):
        costs = [r["cost_usd"] for r, _ in runs if number(r.get("cost_usd"))]
        latencies = sorted(r["latency_ms"] for r, _ in runs if number(r.get("latency_ms")))
        passed = sum(ok for _, ok in runs)
        metrics.append({
            "requested_model": requested, "actual_model": actual, "trials": len(runs),
            "passed": passed, "pass_rate": passed / len(runs),
            "fallback_trials": len(runs) if requested != actual else 0,
            "cost_per_success_usd": sum(costs) / passed if passed and len(costs) == len(runs) else None,
            "p95_latency_ms": latencies[math.ceil(.95 * len(latencies)) - 1] if len(latencies) == len(runs) else None,
        })
    return {"passed": not failures and not missing, "failures": failures,
            "missing_coverage": missing, "metrics": metrics}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path, help="JSON array exported from the trial harness")
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--min-trials", type=int, default=3)
    args = parser.parse_args()
    try:
        result = score(json.loads(args.records.read_text()),
                       json.loads(args.cases.read_text()), args.min_trials)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"passed": False, "error": type(exc).__name__}))
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
