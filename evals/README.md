# Regression tests and agent trials

Run from the repository root, using Python 3.11+ and standard-library modules:

```sh
python3 -m unittest discover -s tests -v
```

This exercises the managed controls and adapters, the outbound log, encrypted recovery
(when age is installed), and the offline scorer. External services use test doubles.
No API key, paid model run, WhatsApp message or live spreadsheet is used.

The GitHub Actions workflow runs the same offline checks on Linux and macOS
with Python 3.11 and 3.13 after a push or pull request. It needs no repository
secrets. Its action versions are pinned to the official
[checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1) and
[setup-python v7.0.0](https://github.com/actions/setup-python/releases/tag/v7.0.0)
releases. Adding the workflow locally does not run GitHub Actions.

## Agent behavior evaluation

cases.json contains eight starter tasks, fault setups and human review rubrics.
These are trial requirements, not claims that every behavior is already automated.
A trial driver must translate actual managed results and errors into the scorer
format without changing their meaning; the repository does not include that live driver.
Run each through the eventual agent runtime against isolated synthetic systems.
Reset the test environment between trials. Keep the same prompt/config revision,
tool set and data when comparing candidates. A default minimum of three trials
per case checks coverage; it is not proof of production reliability.

Export a JSON array with one object per trial:

```json
{
  "case_id": "partial_report",
  "run_id": "run-001",
  "trial_id": "trial-1",
  "requested_model": "provider/exact-model-id",
  "actual_model": "provider/exact-model-id",
  "config_revision": "commit-and-config-digest",
  "provenance": "runtime",
  "fallback_reason": null,
  "fallback_disclosed": false,
  "tool_calls": 5,
  "latency_ms": 1200,
  "cost_usd": 0.02,
  "final_status": "succeeded",
  "result": {
    "status": "succeeded",
    "evidence": [{"source": "spreadsheet", "check": "readback_matched"}]
  },
  "review_passed": true,
  "reviewer": "human-reviewer-id",
  "review_evidence": "local-path-to-sanitized-transcript-and-state-check"
}
```

This is a fictional format example, not an observed run. The actual harness must
collect metadata and tool evidence outside the model's response.

`evals/run.py` is that harness for one trial. It refuses unknown cases and
missing inputs, hashes the input files before and after the run (the
`config_revision` is a sha256 over those hashes, not a git tree), streams the
command's output while keeping a 0600 log under `evals/logs/`, captures the
last tool-result JSON on stdout as `result`, and appends the record to
`evals/records/trials.json`. The command's exit code is the wrapper's exit
code; bookkeeping failures only warn.

```sh
python3 evals/run.py --case sheet_unavailable --requested-model provider/model \
    --input managed/runtime.py --input evals/cases.json \
    -- <the command that runs the trial>
```

The actual model comes from `--actual-model` or from an `actual_model=<id>`
line the runtime prints. A record leaves the wrapper with `review_passed`
false and an empty `reviewer`; a human reads the log against the rubric, fills
both in, and only then does `score.py` accept it. Setting them without reading
the log is the relabeling the scorer cannot detect. For context
cases, the harness records source_read/source_refreshed after observing the
source access and version; for report verification it records report_verified
after checking the artifact. A human reviews the case rubric and records the
verdict. These labels are not built-in OpenClaw events.

```sh
python3 evals/score.py /path/to/sanitized-trials.json
```

The scorer rejects missing metrics, failed reviews, unknown cases, duplicate
trials, wrong statuses, absent required evidence, undisclosed fallback and
insufficient coverage. It groups costs and latency by requested and actual
model; cost includes failed attempts. It validates the supplied record, not the
authenticity of that record: manually relabeling fake data as runtime is not a
real evaluation. It does not load secrets, launch models or wire integrations.

The unit tests use synthetic records to verify the scorer's positive and
negative paths. Their passing result is **not** a passed agent benchmark.
Run the existing manual permission checks unchanged in the live install; this
suite does not redefine authority or certify runtime isolation.
