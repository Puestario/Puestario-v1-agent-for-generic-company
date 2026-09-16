# Model selection and runtime evidence

No model is qualified by this template alone. Profile names such as fast,
standard or deep are local labels; map them to exact available model IDs only
after measurement. Preserve all existing owner, staff and delegation rules.

## Selection procedure

1. Choose representative tasks and define correctness, evidence requirements,
   maximum spend, latency and tool-call budgets before comparing models.
2. Run the same cases with the same tools and source data on each candidate.
   Use repeated trials; the included scorer defaults to at least three per case.
3. Reject a candidate with failed acceptance checks. Among qualifying candidates,
   compare latency and cost per successful task, including failed-run costs.
4. Compare a single-agent baseline with any proposed delegation on the same cases.
   Use additional agents only for a demonstrated benefit.
5. Keep the previous tested model/prompt configuration available for rollback.

Three trials is a starter coverage check, not a statistical reliability guarantee.
Broaden the dataset with actual failures and task variations as they occur.

## Record from the runtime

For each trial, capture run ID, case ID, trial ID, requested model, actual model,
fallback reason, whether fallback was disclosed, tool-call count, elapsed
milliseconds and total model cost in USD across all attempts/workers. Also keep
the prompt/config revision, tool outcomes and a reviewer verdict with an evidence
reference. Use runtime metadata for model IDs and usage, never the model's claim
about itself. Keep raw sensitive data out of committed examples.

The scorer in evals/score.py consumes this record and reports completion of the
suite, pass rate, fallback count, p95 latency and cost per successful task, grouped
by requested and actual model. Missing measurements fail grading rather than
becoming zero cost. The same scorer can run locally on sanitized runtime exports.

This template has no runtime telemetry collector, model routing engine or live
provider integration. Populate records from the eventual runtime; synthetic
fixtures only verify the scorer.

## Fallback and budgets

Preserve the operating rule requiring immediate disclosure of fallback. Record
the actual fallback model and reason. A fallback needs evaluation on the same
task family. Test its tool behavior as well as its output.

Stop at the task's stated budget and return the remaining work explicitly.
Do not start unbounded retries or recreate an uncertain external action to obtain
a nicer status. First reconcile with the external system. More expensive models
and more agents are hypotheses to test, not automatic upgrades.
